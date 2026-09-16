import sqlite3
import requests
import json
import os
import time

API_URL = os.environ.get("BANE_API_URL", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get("BANE_DB_PATH", "enterprise_nexus.sqlite")

test_suite_part_a = [
    {
        "id": 1,
        "title": "Sales Rep Active MRR (3-Table JOIN + Cents Conversion)",
        "question": "Calculate the total active monthly recurring revenue in USD managed by each sales rep, ordered from highest to lowest.",
        "expected_tables": ["tbl_sales_reps", "tbl_account_assignments", "tbl_subscriptions_hist"],
        "expected_sql": """SELECT r.rep_name, r.territory,
       ROUND(SUM(s.mrr_cents) / 100.0, 2) AS active_mrr_usd
FROM tbl_sales_reps r
JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
JOIN tbl_subscriptions_hist s ON aa.acct_id = s.acct_id
WHERE s.cancellation_date IS NULL AND aa.is_primary_owner = 1
GROUP BY r.rep_id, r.rep_name
ORDER BY active_mrr_usd DESC;"""
    },
    {
        "id": 2,
        "title": "VIP Product Category Revenue (4-Table JOIN)",
        "question": "Show me total settled revenue broken down by product category generated exclusively from VIP tier accounts.",
        "expected_tables": ["tbl_accounts", "tbl_transactions_ledger", "tbl_order_items", "tbl_products_catalog"],
        "expected_sql": """SELECT p.category, ROUND(SUM(oi.line_total_usd), 2) AS total_revenue_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
JOIN tbl_order_items oi ON t.tx_id = oi.tx_id
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
WHERE a.tier_segment = 'TIER_1_VIP' AND t.settlement_status = 'SETTLED'
GROUP BY p.category
ORDER BY total_revenue_usd DESC;"""
    },
    {
        "id": 3,
        "title": "Customer Spend Ranking by Country (Window Function DENSE_RANK)",
        "question": "Rank all accounts within their respective country by their total settled spend volume.",
        "expected_tables": ["tbl_accounts", "tbl_transactions_ledger"],
        "expected_sql": """WITH customer_spend AS (
    SELECT a.country_iso3, a.client_legal_name, ROUND(SUM(t.gross_amt_usd), 2) AS total_spent
    FROM tbl_accounts a
    JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
    WHERE t.settlement_status = 'SETTLED'
    GROUP BY a.acct_id
)
SELECT country_iso3, client_legal_name, total_spent,
       DENSE_RANK() OVER (PARTITION BY country_iso3 ORDER BY total_spent DESC) AS country_rank
FROM customer_spend
ORDER BY country_iso3, country_rank;"""
    },
    {
        "id": 4,
        "title": "Gateway Refund Rate & Loss (Conditional Aggregation CASE WHEN)",
        "question": "What is the refund rate percentage and total refunded amount for each payment gateway provider?",
        "expected_tables": ["tbl_transactions_ledger"],
        "expected_sql": """SELECT gateway_provider,
       COUNT(*) AS total_tx_count,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
FROM tbl_transactions_ledger
GROUP BY gateway_provider
ORDER BY refund_pct DESC;"""
    },
    {
        "id": 5,
        "title": "Critical Unresolved Support Blockers (Filter & Multi-column)",
        "question": "List all client accounts currently experiencing open or investigating SEV-1 blocker support cases.",
        "expected_tables": ["tbl_accounts", "tbl_support_cases"],
        "expected_sql": """SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
ORDER BY sc.created_ts ASC;"""
    },
    {
        "id": 6,
        "title": "Support Performance by Agent Tier (Multi-metric Aggregation)",
        "question": "Find the average CSAT score and average response time in minutes for each support agent tier on resolved cases.",
        "expected_tables": ["tbl_support_agents", "tbl_support_cases"],
        "expected_sql": """SELECT sa.tier_level,
       COUNT(sc.case_number) AS total_resolved_cases,
       ROUND(AVG(sc.csat_score), 2) AS avg_csat_score,
       ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_resp_time_mins
FROM tbl_support_agents sa
JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
WHERE sc.case_status = 'RESOLVED' AND sc.csat_score IS NOT NULL
GROUP BY sa.tier_level
ORDER BY sa.tier_level ASC;"""
    },
    {
        "id": 7,
        "title": "Top 5 Heavy Compute Consumers (Time-series Grouping)",
        "question": "Identify the top 5 accounts with the highest cumulative compute hours consumed across all telemetry records.",
        "expected_tables": ["tbl_accounts", "tbl_usage_telemetry"],
        "expected_sql": """SELECT a.client_legal_name, a.tier_segment,
       ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
       SUM(u.api_calls_count) AS total_api_calls
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.acct_id
ORDER BY total_compute_hours DESC
LIMIT 5;"""
    },
    {
        "id": 8,
        "title": "Subscription Churn Reason Analysis (NULL Date Filtering)",
        "question": "Break down lost monthly recurring revenue and total churned contract count by cancellation reason.",
        "expected_tables": ["tbl_subscriptions_hist"],
        "expected_sql": """SELECT cancellation_reason_code,
       COUNT(*) AS churned_contracts_count,
       ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NOT NULL
GROUP BY cancellation_reason_code
ORDER BY lost_mrr_usd DESC;"""
    },
    {
        "id": 9,
        "title": "Top Discounted Product Purchases (3-Table JOIN + Sorting)",
        "question": "Show the top 3 order line items with the highest discount percentage, including product name and total line price.",
        "expected_tables": ["tbl_order_items", "tbl_products_catalog", "tbl_transactions_ledger"],
        "expected_sql": """SELECT oi.line_item_id, p.product_name, oi.quantity,
       oi.discount_pct * 100 AS discount_percent,
       oi.line_total_usd, t.tx_timestamp
FROM tbl_order_items oi
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
WHERE oi.discount_pct > 0
ORDER BY oi.discount_pct DESC, oi.line_total_usd DESC
LIMIT 3;"""
    },
    {
        "id": 10,
        "title": "Sales Rep Quota Attainment (JOIN + HAVING Filter)",
        "question": "Which sales representatives have achieved or exceeded their assigned quota based on settled transactions?",
        "expected_tables": ["tbl_sales_reps", "tbl_account_assignments", "tbl_transactions_ledger"],
        "expected_sql": """SELECT r.rep_name, r.quota_amount_usd,
       ROUND(SUM(t.net_amt_usd), 2) AS total_net_settled_usd,
       ROUND(SUM(t.net_amt_usd) * 100.0 / r.quota_amount_usd, 2) AS quota_attainment_pct
FROM tbl_sales_reps r
JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
GROUP BY r.rep_id
HAVING total_net_settled_usd >= r.quota_amount_usd
ORDER BY quota_attainment_pct DESC;"""
    },
    {
        "id": 11,
        "title": "Anomaly Detection: High 5xx Server Errors (HAVING comparison)",
        "question": "Find all accounts that have experienced more 5xx server errors than 4xx client errors in telemetry.",
        "expected_tables": ["tbl_accounts", "tbl_usage_telemetry"],
        "expected_sql": """SELECT a.client_legal_name,
       SUM(u.error_count_5xx) AS total_5xx_errors,
       SUM(u.error_count_4xx) AS total_4xx_errors
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.acct_id
HAVING total_5xx_errors > total_4xx_errors AND total_5xx_errors > 0
ORDER BY total_5xx_errors DESC;"""
    },
    {
        "id": 12,
        "title": "Account Growth Cohort by Month (STRFTIME)",
        "question": "Show the number of new client accounts created per month in chronological order.",
        "expected_tables": ["tbl_accounts"],
        "expected_sql": """SELECT strftime('%Y-%m', created_at) AS signup_month,
       COUNT(*) AS new_accounts_count
FROM tbl_accounts
GROUP BY signup_month
ORDER BY signup_month ASC;"""
    },
    {
        "id": 13,
        "title": "Payment Gateway Settlement Stats (Min, Max, Avg Net)",
        "question": "Calculate the average, minimum, and maximum net transaction amount for settled charges grouped by payment gateway.",
        "expected_tables": ["tbl_transactions_ledger"],
        "expected_sql": """SELECT gateway_provider,
       COUNT(*) AS settled_tx_count,
       ROUND(AVG(net_amt_usd), 2) AS avg_net_usd,
       ROUND(MIN(net_amt_usd), 2) AS min_net_usd,
       ROUND(MAX(net_amt_usd), 2) AS max_net_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND tx_type = 'CHARGE'
GROUP BY gateway_provider
ORDER BY avg_net_usd DESC;"""
    },
    {
        "id": 14,
        "title": "Multi-Contract Accounts (Count Filtering HAVING COUNT > 1)",
        "question": "Which accounts have signed more than one subscription contract in their company history?",
        "expected_tables": ["tbl_accounts", "tbl_subscriptions_hist"],
        "expected_sql": """SELECT a.client_legal_name, a.tier_segment,
       COUNT(s.sub_contract_id) AS total_contracts_count
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
GROUP BY a.acct_id
HAVING COUNT(s.sub_contract_id) > 1
ORDER BY total_contracts_count DESC;"""
    },
    {
        "id": 15,
        "title": "Best-Selling Add-on Product (Product Category Filter + Unit Aggregation)",
        "question": "What is the single best-selling add-on product by total units sold and how much gross sales did it generate?",
        "expected_tables": ["tbl_order_items", "tbl_products_catalog"],
        "expected_sql": """SELECT p.product_name, p.prod_sku, SUM(oi.quantity) AS total_units_sold,
       ROUND(SUM(oi.line_total_usd), 2) AS total_gross_sales
FROM tbl_order_items oi
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
WHERE p.category IN ('STORAGE_ADDON', 'COMPUTE_BURST')
GROUP BY p.prod_sku
ORDER BY total_units_sold DESC
LIMIT 1;"""
    },
    {
        "id": 16,
        "title": "Support SLA Breach Rate by Severity (Filter + Aggregate)",
        "question": "Group cases where first response time was greater than 60 minutes by severity level, showing count and average response time.",
        "expected_tables": ["tbl_support_cases"],
        "expected_sql": """SELECT severity_level,
       COUNT(*) AS delayed_cases_count,
       ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
FROM tbl_support_cases
WHERE first_response_time_minutes > 60
GROUP BY severity_level
ORDER BY delayed_cases_count DESC;"""
    },
    {
        "id": 17,
        "title": "Cumulative Gross Transaction Volume (Window Function SUM() OVER)",
        "question": "Calculate the cumulative running total of gross transaction volume over time for settled payments.",
        "expected_tables": ["tbl_transactions_ledger"],
        "expected_sql": """SELECT tx_id, tx_timestamp, gross_amt_usd,
       ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED'
LIMIT 10;"""
    },
    {
        "id": 18,
        "title": "Financial Risk: Delinquent Accounts and Chargebacks (OR Logic + ABS)",
        "question": "List all delinquent accounts or accounts with chargeback transactions, displaying total disputed amount.",
        "expected_tables": ["tbl_accounts", "tbl_transactions_ledger"],
        "expected_sql": """SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
       ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
GROUP BY a.acct_id
ORDER BY total_disputed_usd DESC;"""
    },
    {
        "id": 19,
        "title": "Average Storage Consumption per Tier (Grouped Analytics)",
        "question": "What is the average and peak daily storage in gigabytes used by accounts across each tier segment?",
        "expected_tables": ["tbl_accounts", "tbl_usage_telemetry"],
        "expected_sql": """SELECT a.tier_segment,
       ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
       ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.tier_segment
ORDER BY avg_storage_gb DESC;"""
    },
    {
        "id": 20,
        "title": "Overall Net Profit Margin (Gross vs Fees Math)",
        "question": "Calculate our overall net profit margin percentage across all settled transactions after accounting for gateway fees.",
        "expected_tables": ["tbl_transactions_ledger"],
        "expected_sql": """SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
       ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
       ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
       ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;"""
    }
]

def run_evaluation():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    report_lines = [
        "# Part A Benchmark Evaluation: 20 Tough Technical Queries",
        "",
        "> Evaluation conducted against **`enterprise_nexus.sqlite`**.",
        "> This document records the Agent's generated SQL, execution outcome, and a detailed gap analysis vs Ground-Truth SQL for manual review.",
        "",
        "---",
        ""
    ]

    print("Starting evaluation of Part A (20 questions)...")

    for item in test_suite_part_a:
        q_id = item["id"]
        title = item["title"]
        q_text = item["question"]
        expected_sql = item["expected_sql"]
        expected_tables = item["expected_tables"]

        print(f"\nEvaluating Q{q_id:02d}: {title}...")

        # 1. Hit API
        try:
            resp = requests.post(f"{API_URL}/generate_sql", json={"question": q_text}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                gen_sql = data.get("sql", "").strip()
                context_used = data.get("context_used", "")
            else:
                gen_sql = f"-- API ERROR: {resp.status_code} {resp.text}"
                context_used = ""
        except Exception as e:
            gen_sql = f"-- CONNECTION ERROR: {e}"
            context_used = ""

        # 2. Check Execution of Generated SQL
        gen_exec_status = "SUCCESS"
        gen_error = None
        gen_rows = []
        try:
            cursor.execute(gen_sql)
            gen_rows = cursor.fetchall()
        except Exception as e:
            gen_exec_status = "EXECUTION_ERROR"
            gen_error = str(e)

        # 3. Check Execution of Expected SQL
        cursor.execute(expected_sql)
        exp_rows = cursor.fetchall()

        # 4. Analyze Gaps & Issues
        issues = []

        # Check table coverage
        retrieved_tables_in_context = [t for t in expected_tables if t in context_used]
        missing_tables_in_context = [t for t in expected_tables if t not in context_used]
        if missing_tables_in_context:
            issues.append(f"**Schema Retrieval (FAISS):** Context missed table(s): `{', '.join(missing_tables_in_context)}`.")

        if gen_exec_status == "EXECUTION_ERROR":
            issues.append(f"**SQL Syntax/Execution:** Query failed to execute in SQLite: `{gen_error}`.")

        # Check for joins if expected
        if len(expected_tables) > 1 and "JOIN" not in gen_sql.upper():
            issues.append(f"**Missing Multi-Table JOIN:** Required {len(expected_tables)}-table JOIN across `{', '.join(expected_tables)}`, but generated query queried only a single table.")

        # Check for aggregations/group by if expected
        if "GROUP BY" in expected_sql.upper() and "GROUP BY" not in gen_sql.upper():
            issues.append("**Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.")

        # Check for window functions if expected
        if "OVER (" in expected_sql.upper() and "OVER (" not in gen_sql.upper():
            issues.append("**Missing Window Function:** Expected Window function (`DENSE_RANK() OVER` or `SUM() OVER`), but generated query used standard SELECT.")

        # Check for specific calculations (cents conversion)
        if "mrr_cents" in expected_sql and "/ 100" in expected_sql and "/ 100" not in gen_sql:
            issues.append("**Unit Mismatch:** Did not convert `mrr_cents` to USD dollars (`/ 100.0`).")

        # Check for conditional case when
        if "CASE WHEN" in expected_sql.upper() and "CASE WHEN" not in gen_sql.upper():
            issues.append("**Missing Conditional Logic:** Expected `CASE WHEN` conditional aggregation.")

        if not issues and gen_exec_status == "SUCCESS":
            issues.append("✔ **Query Executed Cleanly.** Schema and basic intent aligned.")

        # 5. Append to Report
        report_lines.append(f"## Question {q_id}: {title}")
        report_lines.append(f"**Prompt:** *\"{q_text}\"*")
        report_lines.append("")
        report_lines.append("### 🤖 Agent Generated SQL:")
        report_lines.append("```sql")
        report_lines.append(gen_sql)
        report_lines.append("```")
        report_lines.append(f"* **Execution Status:** `{gen_exec_status}` ({len(gen_rows)} rows returned)" + (f" | Error: `{gen_error}`" if gen_error else ""))
        report_lines.append("")
        report_lines.append("### 🎯 Ground-Truth Target SQL:")
        report_lines.append("```sql")
        report_lines.append(expected_sql.strip())
        report_lines.append("```")
        report_lines.append(f"* **Expected Result:** {len(exp_rows)} rows returned from ground-truth query.")
        report_lines.append("")
        report_lines.append("### 🔍 Problems & Gap Analysis for Review:")
        for iss in issues:
            report_lines.append(f"- {iss}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    conn.close()

    # Write report file
    report_file = "BENCHMARK_PART_A_EVALUATION.md"
    with open(report_file, "w") as f:
        f.write("\n".join(report_lines))

    print(f"\n✔ Evaluation complete! Full review sheet written to: {os.path.abspath(report_file)}")

if __name__ == "__main__":
    run_evaluation()
