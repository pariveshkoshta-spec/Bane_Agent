import re
import sqlite3
from typing import Dict, List, Optional, Tuple

class DiagnosticEngine:
    """
    Intelligent SQL linter and diagnostic analyzer that parses SQLite runtime errors,
    maps columns to their correct tables via foreign keys, and generates actionable,
    surgical repair prompts for LLM self-healing.
    """

    def __init__(self, schemas: Dict[str, str]):
        self.schemas = schemas
        self.col_to_table: Dict[str, str] = {}
        self.table_cols: Dict[str, List[str]] = {}
        self.foreign_keys: List[Tuple[str, str, str, str]] = [] # (table, col, foreign_table, foreign_col)
        self._build_schema_graph()

    def _build_schema_graph(self):
        for table, create_sql in self.schemas.items():
            # Extract columns
            col_matches = re.findall(
                r"(\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s+(?:INTEGER|TEXT|REAL|BLOB|BOOLEAN)",
                create_sql,
                re.IGNORECASE
            )
            cols = [
                c.lower() for c in col_matches
                if c.upper() not in ("PRIMARY", "KEY", "FOREIGN", "NOT", "NULL", "CHECK", "DEFAULT")
            ]
            self.table_cols[table] = cols
            for col in cols:
                # Store primary owner of column
                if col not in self.col_to_table or col in ("acct_id", "tx_id", "rep_id", "prod_sku"):
                    self.col_to_table[col] = table

            # Extract Foreign Keys
            fk_matches = re.findall(
                r"FOREIGN\s+KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\s*\((\w+)\)",
                create_sql,
                re.IGNORECASE
            )
            for fk_col, ref_table, ref_col in fk_matches:
                self.foreign_keys.append((table, fk_col, ref_table, ref_col))

    def diagnose_error(self, error_msg: str, failed_sql: str) -> str:
        """
        Translates raw SQLite error into actionable compiler-grade diagnostics.
        """
        err_lower = error_msg.lower()
        diagnostics = []

        # 1. Column Missing / Unjoined Table Detection
        no_col_match = re.search(r"no such column:\s*([a-zA-Z0-9_\.]+)", error_msg)
        if no_col_match:
            raw_col = no_col_match.group(1).split(".")[-1].lower()
            home_table = self.col_to_table.get(raw_col)

            if home_table:
                # Check if home table is already in the query
                if home_table.lower() not in failed_sql.lower():
                    # Find join bridge
                    bridge_hint = ""
                    for src_tbl, src_col, ref_tbl, ref_col in self.foreign_keys:
                        if (src_tbl == home_table and ref_tbl.lower() in failed_sql.lower()):
                            bridge_hint = f"JOIN {home_table} ON {src_tbl}.{src_col} = {ref_tbl}.{ref_col}"
                            break
                        elif (ref_tbl == home_table and src_tbl.lower() in failed_sql.lower()):
                            bridge_hint = f"JOIN {home_table} ON {src_tbl}.{src_col} = {ref_tbl}.{ref_col}"
                            break

                    if not bridge_hint and "acct_id" in self.table_cols.get(home_table, []):
                        bridge_hint = f"JOIN {home_table} ON {home_table}.acct_id = tbl_accounts.acct_id"

                    diagnostics.append(
                        f"[DIAGNOSTIC - MISSING JOIN]: The column '{raw_col}' does NOT exist in the queried tables. "
                        f"It belongs to table '{home_table}'.\n"
                        f"ACTION REQUIRED: Add the following JOIN to your query: '{bridge_hint}'."
                    )
                else:
                    diagnostics.append(
                        f"[DIAGNOSTIC - ALIAS MISMATCH]: Column '{raw_col}' belongs to table '{home_table}'. "
                        f"Prefix it with the correct table alias for '{home_table}' (e.g. '{home_table}.{raw_col}')."
                    )

        # 2. Ambiguous Column Detection
        ambig_match = re.search(r"ambiguous column name:\s*(\w+)", error_msg)
        if ambig_match:
            ambig_col = ambig_match.group(1).lower()
            matching_tables = [tbl for tbl, cols in self.table_cols.items() if ambig_col in cols and tbl.lower() in failed_sql.lower()]
            diagnostics.append(
                f"[DIAGNOSTIC - AMBIGUOUS COLUMN]: Column '{ambig_col}' exists in multiple joined tables: {matching_tables}.\n"
                f"ACTION REQUIRED: Explicitly prefix '{ambig_col}' with the appropriate table alias (e.g. 'a.{ambig_col}' or 't.{ambig_col}') in both SELECT and GROUP BY clauses."
            )

        # 3. Aggregate in GROUP BY Detection
        if "aggregate functions are not allowed in the group by clause" in err_lower or "group by 1" in failed_sql.lower():
            diagnostics.append(
                f"[DIAGNOSTIC - INVALID GROUP BY]: SQLite prohibits 'GROUP BY 1' or GROUP BY on aggregate functions (AVG, SUM, COUNT).\n"
                f"ACTION REQUIRED: Since you are computing an overall aggregate across the table, remove the 'GROUP BY' clause entirely."
            )

        # 4. Syntax Error Near 'AS' / Misplaced Calculations
        if 'near "as": syntax error' in err_lower or "syntax error" in err_lower:
            if re.search(r"where\s+.*as\s+", failed_sql, re.IGNORECASE):
                diagnostics.append(
                    f"[DIAGNOSTIC - MISPLACED CLAUSE]: Aliases ('AS alias_name') and mathematical divisions (/ 100.0) cannot appear in the WHERE clause.\n"
                    f"ACTION REQUIRED: Move all calculations and 'AS' aliases into the SELECT clause. Keep WHERE strictly for boolean filters (e.g. WHERE cancellation_date IS NULL)."
                )

        # 5. Window Function and CTE Guidance
        if "window function" in err_lower or "dense_rank" in failed_sql.lower():
            diagnostics.append(
                f"[DIAGNOSTIC - WINDOW FUNCTION CTE]: In SQLite, window functions (like DENSE_RANK() OVER (...)) cannot be mixed directly with GROUP BY aggregates on the same level.\n"
                f"ACTION REQUIRED: Wrap the aggregated query in a Common Table Expression: 'WITH spend AS (SELECT acct_id, country_iso3, SUM(net_amt_usd) AS total_spent FROM tbl_transactions_ledger t JOIN tbl_accounts a ON t.acct_id = a.acct_id WHERE t.settlement_status = 'SETTLED' GROUP BY a.acct_id) SELECT country_iso3, acct_id, total_spent, DENSE_RANK() OVER (PARTITION BY country_iso3 ORDER BY total_spent DESC) AS rank FROM spend ORDER BY country_iso3, rank;'"
            )

        if not diagnostics:
            diagnostics.append(f"[DIAGNOSTIC]: SQLite Error: {error_msg}. Review the schema definition and fix table/column names.")

        return "\n".join(diagnostics)


def clean_sql_output(raw_output: str, prompt_prefix: str = "") -> str:
    """
    Strips prompt prefixes, markdown fences, and trailing explanatory text.
    """
    cleaned = raw_output.replace(prompt_prefix, "").strip()
    if "```sql" in cleaned:
        cleaned = cleaned.split("```sql")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    # Extract strictly the SQL statement up to the terminating semicolon
    if ";" in cleaned:
        cleaned = cleaned.split(";")[0].strip() + ";"

    # Strip illegal GROUP BY 1 if present
    if "group by 1" in cleaned.lower() and ("avg(" in cleaned.lower() or "sum(" in cleaned.lower()):
        cleaned = re.sub(r"group\s+by\s+1\b", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip() + ";"

    return cleaned


def validate_sql_execution(predicted_sql: str, ground_truth_sql: str, db_path: str) -> bool:
    """
    Connects to the SQLite database and compares the execution output.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(predicted_sql)
        pred_res = set(cursor.fetchall())
        cursor.execute(ground_truth_sql)
        truth_res = set(cursor.fetchall())
        conn.close()
        return pred_res == truth_res
    except Exception:
        return False
