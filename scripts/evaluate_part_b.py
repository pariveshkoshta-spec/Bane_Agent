import sqlite3
import requests
import json
import os

API_URL = os.environ.get("BANE_API_URL", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get("BANE_DB_PATH", "enterprise_nexus.sqlite")

part_b_questions = [
    {
        "id": 21,
        "title": "Big Whales Who Cancelled",
        "question": "Who are our biggest whales that cancelled on us and what excuse did they give?",
        "expected_sql": """SELECT a.client_legal_name, s.plan_code, ROUND(s.mrr_cents / 100.0, 2) AS lost_mrr_usd,
       s.cancellation_date, s.cancellation_reason_code
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
WHERE s.cancellation_date IS NOT NULL AND a.tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')
ORDER BY s.mrr_cents DESC;""",
        "expected_explanation": "Translates non-tech slang 'biggest whales' to VIP/Enterprise tiers, maps 'cancelled' to non-null cancellation_date, and selects reason codes ordered by lost revenue."
    },
    {
        "id": 22,
        "title": "Top Cash Producer Sales Rep",
        "question": "Which sales rep is crushing it the most this year in terms of actual settled cash, not just contracts?",
        "expected_sql": """SELECT r.rep_name, r.territory, ROUND(SUM(t.net_amt_usd), 2) AS total_cash_settled_usd
FROM tbl_sales_reps r
JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
GROUP BY r.rep_id
ORDER BY total_cash_settled_usd DESC
LIMIT 1;""",
        "expected_explanation": "Decodes 'crushing it in settled cash' to maximum sum of net_amt_usd with settlement_status = 'SETTLED' grouped by rep."
    },
    {
        "id": 23,
        "title": "Bleeding Accounts (Refunds > Charges)",
        "question": "Show me accounts that are bleeding us money with more refunds than actual charges.",
        "expected_sql": """SELECT a.client_legal_name,
       SUM(CASE WHEN t.tx_type = 'REFUND' THEN 1 ELSE 0 END) AS refund_count,
       SUM(CASE WHEN t.tx_type = 'CHARGE' THEN 1 ELSE 0 END) AS charge_count,
       ROUND(SUM(t.gross_amt_usd), 2) AS net_balance_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
GROUP BY a.acct_id
HAVING refund_count > charge_count;""",
        "expected_explanation": "Translates 'bleeding us money' into conditional aggregation comparing count of refunds vs charges per account with HAVING."
    },
    {
        "id": 24,
        "title": "VIP Clients with Terrible Support Reviews",
        "question": "Find the VIP clients who had terrible support experience lately with really bad review scores.",
        "expected_sql": """SELECT a.client_legal_name, sc.case_number, sc.csat_score, sc.severity_level, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE a.tier_segment = 'TIER_1_VIP' AND sc.csat_score <= 2
ORDER BY sc.csat_score ASC, sc.created_ts DESC;""",
        "expected_explanation": "Maps 'VIP clients' to tier_segment = 'TIER_1_VIP' and 'bad review scores' to csat_score <= 2, joining accounts with support cases."
    },
    {
        "id": 25,
        "title": "Total MRR in Plain Dollars",
        "question": "What's our total monthly recurring revenue right now in plain dollars, not pennies?",
        "expected_sql": """SELECT ROUND(SUM(mrr_cents) / 100.0, 2) AS total_active_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NULL;""",
        "expected_explanation": "Understands 'plain dollars, not pennies' requires dividing mrr_cents by 100.0 for active subscriptions."
    },
    {
        "id": 26,
        "title": "Silent Sufferers (Errors with No Ticket)",
        "question": "Are there any accounts getting hammered with server errors but nobody filed a ticket for them?",
        "expected_sql": """SELECT a.client_legal_name, SUM(u.error_count_5xx) AS total_server_errors
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
LEFT JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE sc.case_number IS NULL
GROUP BY a.acct_id
HAVING total_server_errors > 0
ORDER BY total_server_errors DESC;""",
        "expected_explanation": "Understands 'nobody filed a ticket' implies a LEFT JOIN on tbl_support_cases with WHERE sc.case_number IS NULL and positive 5xx errors."
    },
    {
        "id": 27,
        "title": "Add-ons Bundled with Enterprise Plans",
        "question": "Which products are driving the most money when bundled with our big enterprise plans?",
        "expected_sql": """SELECT p.product_name, p.category, ROUND(SUM(oi.line_total_usd), 2) AS gross_sales_usd
FROM tbl_order_items oi
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
JOIN tbl_subscriptions_hist s ON t.sub_contract_id = s.sub_contract_id
WHERE s.plan_code = 'PLAN_ENT_CUSTOM'
GROUP BY p.prod_sku
ORDER BY gross_sales_usd DESC;""",
        "expected_explanation": "Links products, order items, transactions, and subscriptions with plan_code = 'PLAN_ENT_CUSTOM'."
    },
    {
        "id": 28,
        "title": "Delinquent European Clients",
        "question": "Give me a list of folks in Europe who haven't paid their bills and are suspended.",
        "expected_sql": """SELECT client_legal_name, contact_person, contact_email, country_iso3, acct_status_flg
FROM tbl_accounts
WHERE country_iso3 IN ('DEU', 'GBR', 'FRA') AND acct_status_flg IN ('S', 'D');""",
        "expected_explanation": "Translates 'Europe' to European ISO codes (DEU, GBR, FRA) and 'haven't paid and suspended' to status flags 'S' and 'D'."
    },
    {
        "id": 29,
        "title": "Slowest Agent on Critical Outages",
        "question": "Who is our slowest support agent to reply when a customer has a critical emergency blocker?",
        "expected_sql": """SELECT sa.agent_full_name, sa.region,
       ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_blocker_response_mins,
       COUNT(*) AS blocker_cases_handled
FROM tbl_support_agents sa
JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
WHERE sc.severity_level = 'SEV_1_BLOCKER'
GROUP BY sa.agent_id
ORDER BY avg_blocker_response_mins DESC
LIMIT 1;""",
        "expected_explanation": "Translates 'critical emergency blocker' to SEV_1_BLOCKER and 'slowest support agent' to MAX(AVG(first_response_time_minutes))."
    },
    {
        "id": 30,
        "title": "Cheap Tier Heavy Compute Hogs",
        "question": "Which accounts used an insane amount of compute hours last week but are only on our cheap starter tier?",
        "expected_sql": """SELECT a.client_legal_name, a.tier_segment,
       ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
       SUM(u.api_calls_count) AS total_api_calls
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
WHERE a.tier_segment = 'TIER_4_SMB'
GROUP BY a.acct_id
ORDER BY total_compute_hours DESC
LIMIT 5;""",
        "expected_explanation": "Translates 'cheap starter tier' to TIER_4_SMB and 'insane amount of compute hours' to ORDER BY SUM(compute_hours_consumed) DESC."
    }
]

def run_part_b():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    results = []
    print("Evaluating Part B (10 messy conversational questions)...")

    for item in part_b_questions:
        q_id = item["id"]
        title = item["title"]
        q_text = item["question"]
        expected_sql = item["expected_sql"]
        expected_exp = item["expected_explanation"]

        print(f"Testing Q{q_id}: {title}...")

        # 1. Hit API
        try:
            resp = requests.post(f"{API_URL}/generate_sql", json={"question": q_text}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                gen_sql = data.get("sql", "").strip()
            else:
                gen_sql = f"-- API ERROR: {resp.status_code}"
        except Exception as e:
            gen_sql = f"-- CONNECTION ERROR: {e}"

        # 2. Test Execution of Generated SQL
        status = "SUCCESS"
        err = None
        rows = []
        try:
            cursor.execute(gen_sql)
            rows = cursor.fetchall()
        except Exception as e:
            status = "EXECUTION_ERROR"
            err = str(e)

        # 3. Analyze specific fault
        faults = []
        if status == "EXECUTION_ERROR":
            faults.append(f"Execution crashed: `{err}`")

        # Semantic breakdown
        if "whales" in q_text.lower() and "TIER_1_VIP" not in gen_sql:
            faults.append("Semantic Failure: Did not understand non-tech slang 'whales' (failed to filter for VIP/Enterprise accounts).")
        if "crushing it" in q_text.lower() and "SUM" not in gen_sql:
            faults.append("Semantic Failure: Did not translate business slang 'crushing it in settled cash' into SUM(net_amt_usd) with SETTLED filter.")
        if "bleeding" in q_text.lower() and "HAVING" not in gen_sql:
            faults.append("Semantic Failure: Did not translate 'bleeding us money' into HAVING refund_count > charge_count.")
        if "bad review" in q_text.lower() and "csat_score" not in gen_sql:
            faults.append("Semantic Failure: Missed mapping 'bad review scores' to csat_score <= 2.")
        if "pennies" in q_text.lower() and "/ 100" not in gen_sql:
            faults.append("Math & Unit Failure: Ignored user's explicit request for 'plain dollars, not pennies' (failed to divide mrr_cents by 100.0).")
        if "nobody filed a ticket" in q_text.lower() and "LEFT JOIN" not in gen_sql:
            faults.append("Relational Logic Failure: Failed to apply LEFT JOIN with NULL check to identify silent sufferers without support cases.")
        if "Europe" in q_text.lower() and "country_iso3" not in gen_sql:
            faults.append("Geographic Entity Failure: Failed to map 'Europe' to European ISO3 country codes (DEU, GBR, FRA).")
        if "slowest" in q_text.lower() and "AVG" not in gen_sql:
            faults.append("Ranking Failure: Failed to calculate average response time and sort descending to find the slowest agent.")
        if "cheap starter" in q_text.lower() and "TIER_4_SMB" not in gen_sql:
            faults.append("Tier Mapping Failure: Failed to map 'cheap starter tier' to TIER_4_SMB.")

        if "JOIN" in expected_sql and "JOIN" not in gen_sql:
            faults.append("Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.")

        results.append({
            "id": q_id,
            "title": title,
            "question": q_text,
            "agent_sql": gen_sql,
            "fault": "\n".join(f"{i+1}. {f}" for i, f in enumerate(faults)) if faults else "Basic single-table query generated without full relational complexity.",
            "expected_sql": expected_sql,
            "expected_explanation": expected_exp,
            "status": status,
            "rows": len(rows)
        })

    conn.close()
    return results

if __name__ == "__main__":
    results = run_part_b()
    with open("scripts/part_b_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✔ Part B evaluation complete and results cached.")
