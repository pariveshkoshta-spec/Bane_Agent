import os

eval_data = [
    {
        "id": 1,
        "title": "Sales Rep Active MRR",
        "question": "Calculate the total active monthly recurring revenue in USD managed by each sales rep, ordered from highest to lowest.",
        "agent_sql": "SELECT * FROM tbl_subscriptions_hist ORDER BY 1 DESC LIMIT 5;",
        "fault": "1. Queried tbl_subscriptions_hist in isolation, completely missing tbl_sales_reps and the junction table tbl_account_assignments.\n2. Did not group by sales rep (GROUP BY r.rep_id).\n3. Missed the business logic of converting mrr_cents to USD (requires dividing by 100.0).\n4. Failed to filter for active contracts only (cancellation_date IS NULL).",
        "expected_sql": """SELECT r.rep_name, r.territory,
       ROUND(SUM(s.mrr_cents) / 100.0, 2) AS active_mrr_usd
FROM tbl_sales_reps r
JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
JOIN tbl_subscriptions_hist s ON aa.acct_id = s.acct_id
WHERE s.cancellation_date IS NULL AND aa.is_primary_owner = 1
GROUP BY r.rep_id, r.rep_name
ORDER BY active_mrr_usd DESC;""",
        "expected_explanation": "Requires a 3-table join traversing reps -> account assignments -> active subscriptions, summing mrr_cents divided by 100 to produce actual dollar amounts per sales rep."
    },
    {
        "id": 2,
        "title": "VIP Product Category Revenue",
        "question": "Show me total settled revenue broken down by product category generated exclusively from VIP tier accounts.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_order_items;",
        "fault": "1. Returned a single count of order items instead of grouping revenue by product category.\n2. Missed the 4-table join required: tbl_accounts -> tbl_transactions_ledger -> tbl_order_items -> tbl_products_catalog.\n3. Completely omitted the filter for VIP accounts (tier_segment = 'TIER_1_VIP') and settled status (settlement_status = 'SETTLED').",
        "expected_sql": """SELECT p.category, ROUND(SUM(oi.line_total_usd), 2) AS total_revenue_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
JOIN tbl_order_items oi ON t.tx_id = oi.tx_id
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
WHERE a.tier_segment = 'TIER_1_VIP' AND t.settlement_status = 'SETTLED'
GROUP BY p.category
ORDER BY total_revenue_usd DESC;""",
        "expected_explanation": "Links 4 tables to trace product categories purchased by VIP accounts that resulted in settled ledger transactions."
    },
    {
        "id": 3,
        "title": "Customer Spend Ranking by Country",
        "question": "Rank all accounts within their respective country by their total settled spend volume.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_account_assignments;",
        "fault": "1. Hit the wrong table (tbl_account_assignments) instead of tbl_accounts and tbl_transactions_ledger.\n2. Has no concept of analytical Window Functions (DENSE_RANK() OVER (PARTITION BY ...)).\n3. Did not group customer spend or calculate rank.",
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
ORDER BY country_iso3, country_rank;""",
        "expected_explanation": "Requires an initial CTE to aggregate spend per account, followed by a window function partitioning by country to rank accounts from highest to lowest spend."
    },
    {
        "id": 4,
        "title": "Gateway Refund Rate & Loss",
        "question": "What is the refund rate percentage and total refunded amount for each payment gateway provider?",
        "agent_sql": "SELECT * FROM tbl_transactions_ledger;",
        "fault": "1. Dumped the raw transaction ledger without grouping.\n2. Missed GROUP BY gateway_provider.\n3. Missing conditional aggregation (SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END)) to calculate refund percentage vs total transactions.",
        "expected_sql": """SELECT gateway_provider,
       COUNT(*) AS total_tx_count,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
FROM tbl_transactions_ledger
GROUP BY gateway_provider
ORDER BY refund_pct DESC;""",
        "expected_explanation": "Uses conditional CASE WHEN to count refunds separately from total transactions, computing both the percentage rate and absolute loss per provider."
    },
    {
        "id": 5,
        "title": "Critical Unresolved Support Blockers",
        "question": "List all client accounts currently experiencing open or investigating SEV-1 blocker support cases.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_support_cases;",
        "fault": "1. Returned an aggregate COUNT instead of listing the actual accounts.\n2. Did not join tbl_accounts to get client legal name, contact email, and account tier.\n3. Failed to filter for severity_level = 'SEV_1_BLOCKER' and active status in ('OPEN', 'INVESTIGATING').",
        "expected_sql": """SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
ORDER BY sc.created_ts ASC;""",
        "expected_explanation": "Joins accounts to support cases with exact filters on severity and status to highlight active production blockers with client contact details."
    },
    {
        "id": 6,
        "title": "Support Performance by Agent Tier",
        "question": "Find the average CSAT score and average response time in minutes for each support agent tier on resolved cases.",
        "agent_sql": "SELECT * FROM tbl_support_cases LIMIT 20;",
        "fault": "1. Simple select on cases table with limit 20.\n2. Missed join to tbl_support_agents to get agent tier_level.\n3. Missed GROUP BY sa.tier_level and AVG(sc.csat_score) / AVG(sc.first_response_time_minutes).",
        "expected_sql": """SELECT sa.tier_level,
       COUNT(sc.case_number) AS total_resolved_cases,
       ROUND(AVG(sc.csat_score), 2) AS avg_csat_score,
       ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_resp_time_mins
FROM tbl_support_agents sa
JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
WHERE sc.case_status = 'RESOLVED' AND sc.csat_score IS NOT NULL
GROUP BY sa.tier_level
ORDER BY sa.tier_level ASC;""",
        "expected_explanation": "Connects agents to tickets, filters for resolved tickets with non-null CSAT, and groups by tier level."
    },
    {
        "id": 7,
        "title": "Top 5 Heavy Compute Consumers",
        "question": "Identify the top 5 accounts with the highest cumulative compute hours consumed across all telemetry records.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;",
        "fault": "1. Returned a count of telemetry rows.\n2. Missed join to tbl_accounts for client legal name.\n3. Did not group by account or sum compute_hours_consumed.\n4. Missed ORDER BY ... DESC LIMIT 5.",
        "expected_sql": """SELECT a.client_legal_name, a.tier_segment,
       ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
       SUM(u.api_calls_count) AS total_api_calls
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.acct_id
ORDER BY total_compute_hours DESC
LIMIT 5;""",
        "expected_explanation": "Aggregates time-series compute metrics across days for each account and ranks top 5."
    },
    {
        "id": 8,
        "title": "Subscription Churn Reason Analysis",
        "question": "Break down lost monthly recurring revenue and total churned contract count by cancellation reason.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;",
        "fault": "1. Counted all subscription contracts without grouping.\n2. Missed GROUP BY cancellation_reason_code.\n3. Missed filtering for cancelled contracts (cancellation_date IS NOT NULL).\n4. Missed converting mrr_cents to USD dollars (/ 100.0).",
        "expected_sql": """SELECT cancellation_reason_code,
       COUNT(*) AS churned_contracts_count,
       ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NOT NULL
GROUP BY cancellation_reason_code
ORDER BY lost_mrr_usd DESC;""",
        "expected_explanation": "Filters only cancelled records, groups by reason code, and calculates total lost MRR in dollars."
    },
    {
        "id": 9,
        "title": "Top Discounted Product Purchases",
        "question": "Show the top 3 order line items with the highest discount percentage, including product name and total line price.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_order_items;",
        "fault": "1. Returned row count of order items.\n2. Missed 3-table join: tbl_order_items -> tbl_products_catalog -> tbl_transactions_ledger.\n3. Missed ORDER BY discount_pct DESC LIMIT 3.",
        "expected_sql": """SELECT oi.line_item_id, p.product_name, oi.quantity,
       oi.discount_pct * 100 AS discount_percent,
       oi.line_total_usd, t.tx_timestamp
FROM tbl_order_items oi
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
WHERE oi.discount_pct > 0
ORDER BY oi.discount_pct DESC, oi.line_total_usd DESC
LIMIT 3;""",
        "expected_explanation": "Brings product name and transaction date alongside line-item discount details."
    },
    {
        "id": 10,
        "title": "Sales Rep Quota Attainment",
        "question": "Which sales representatives have achieved or exceeded their assigned quota based on settled transactions?",
        "agent_sql": "SELECT * FROM tbl_sales_reps LIMIT 20;",
        "fault": "1. Dumped the sales reps table without transaction data.\n2. Missed 3-table join: reps -> assignments -> transactions.\n3. Missed HAVING total_net_settled_usd >= quota_amount_usd.",
        "expected_sql": """SELECT r.rep_name, r.quota_amount_usd,
       ROUND(SUM(t.net_amt_usd), 2) AS total_net_settled_usd,
       ROUND(SUM(t.net_amt_usd) * 100.0 / r.quota_amount_usd, 2) AS quota_attainment_pct
FROM tbl_sales_reps r
JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
GROUP BY r.rep_id
HAVING total_net_settled_usd >= r.quota_amount_usd
ORDER BY quota_attainment_pct DESC;""",
        "expected_explanation": "Sums net settled cash for each rep's primary accounts and filters by attainment ratio using HAVING."
    },
    {
        "id": 11,
        "title": "Anomaly Detection: High 5xx Server Errors",
        "question": "Find all accounts that have experienced more 5xx server errors than 4xx client errors in telemetry.",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;",
        "fault": "1. Returned count of rows.\n2. Missed join to tbl_accounts for company name.\n3. Missed HAVING SUM(error_count_5xx) > SUM(error_count_4xx).",
        "expected_sql": """SELECT a.client_legal_name,
       SUM(u.error_count_5xx) AS total_5xx_errors,
       SUM(u.error_count_4xx) AS total_4xx_errors
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.acct_id
HAVING total_5xx_errors > total_4xx_errors AND total_5xx_errors > 0
ORDER BY total_5xx_errors DESC;""",
        "expected_explanation": "Compares aggregated server error count against client error count per account."
    },
    {
        "id": 12,
        "title": "Account Growth Cohort by Month",
        "question": "Show the number of new client accounts created per month in chronological order.",
        "agent_sql": "SELECT * FROM tbl_accounts;",
        "fault": "1. Returned all accounts without date aggregation.\n2. Missed SQLite date formatting function strftime('%Y-%m', created_at).\n3. Missed GROUP BY signup_month ORDER BY signup_month ASC.",
        "expected_sql": """SELECT strftime('%Y-%m', created_at) AS signup_month,
       COUNT(*) AS new_accounts_count
FROM tbl_accounts
GROUP BY signup_month
ORDER BY signup_month ASC;""",
        "expected_explanation": "Groups account timestamps by Year-Month to generate a monthly customer growth curve."
    },
    {
        "id": 13,
        "title": "Payment Gateway Settlement Stats",
        "question": "Calculate the average, minimum, and maximum net transaction amount for settled charges grouped by payment gateway.",
        "agent_sql": "SELECT * FROM tbl_transactions_ledger;",
        "fault": "1. Selected raw rows from transactions.\n2. Missed GROUP BY gateway_provider.\n3. Missed calculating AVG, MIN, and MAX on net_amt_usd with filters on SETTLED and CHARGE.",
        "expected_sql": """SELECT gateway_provider,
       COUNT(*) AS settled_tx_count,
       ROUND(AVG(net_amt_usd), 2) AS avg_net_usd,
       ROUND(MIN(net_amt_usd), 2) AS min_net_usd,
       ROUND(MAX(net_amt_usd), 2) AS max_net_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND tx_type = 'CHARGE'
GROUP BY gateway_provider
ORDER BY avg_net_usd DESC;""",
        "expected_explanation": "Evaluates payment gateway performance by calculating statistical spreads on settled charges."
    },
    {
        "id": 14,
        "title": "Multi-Contract Accounts",
        "question": "Which accounts have signed more than one subscription contract in their company history?",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;",
        "fault": "1. Returned count of subscription rows.\n2. Missed join to tbl_accounts for company name and tier.\n3. Missed GROUP BY a.acct_id HAVING COUNT(sub_contract_id) > 1.",
        "expected_sql": """SELECT a.client_legal_name, a.tier_segment,
       COUNT(s.sub_contract_id) AS total_contracts_count
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
GROUP BY a.acct_id
HAVING COUNT(s.sub_contract_id) > 1
ORDER BY total_contracts_count DESC;""",
        "expected_explanation": "Identifies recurring or expanding clients with multiple historical contracts."
    },
    {
        "id": 15,
        "title": "Best-Selling Add-on Product",
        "question": "What is the single best-selling add-on product by total units sold and how much gross sales did it generate?",
        "agent_sql": "SELECT COUNT(*) AS total_count FROM tbl_products_catalog;",
        "fault": "1. Hit products catalog instead of joining order items for units sold.\n2. Missed category filter ('STORAGE_ADDON', 'COMPUTE_BURST').\n3. Missed SUM(oi.quantity) and ORDER BY total_units_sold DESC LIMIT 1.",
        "expected_sql": """SELECT p.product_name, p.prod_sku, SUM(oi.quantity) AS total_units_sold,
       ROUND(SUM(oi.line_total_usd), 2) AS total_gross_sales
FROM tbl_order_items oi
JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
WHERE p.category IN ('STORAGE_ADDON', 'COMPUTE_BURST')
GROUP BY p.prod_sku
ORDER BY total_units_sold DESC
LIMIT 1;""",
        "expected_explanation": "Joins products with order items, filters add-on categories, and aggregates units sold."
    },
    {
        "id": 16,
        "title": "Support SLA Breach Rate by Severity",
        "question": "Group cases where first response time was greater than 60 minutes by severity level, showing count and average response time.",
        "agent_sql": "SELECT * FROM tbl_support_cases LIMIT 20;",
        "fault": "1. Selected arbitrary 20 cases.\n2. Missed WHERE first_response_time_minutes > 60.\n3. Missed GROUP BY severity_level and AVG(first_response_time_minutes).",
        "expected_sql": """SELECT severity_level,
       COUNT(*) AS delayed_cases_count,
       ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
FROM tbl_support_cases
WHERE first_response_time_minutes > 60
GROUP BY severity_level
ORDER BY delayed_cases_count DESC;""",
        "expected_explanation": "Groups ticket SLA breaches by severity to measure impact on customer response."
    },
    {
        "id": 17,
        "title": "Cumulative Gross Transaction Volume",
        "question": "Calculate the cumulative running total of gross transaction volume over time for settled payments.",
        "agent_sql": "SELECT * FROM tbl_transactions_ledger;",
        "fault": "1. Returned raw transaction rows.\n2. Missed window function SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS UNBOUNDED PRECEDING).",
        "expected_sql": """SELECT tx_id, tx_timestamp, gross_amt_usd,
       ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED'
LIMIT 10;""",
        "expected_explanation": "Uses an analytical window function to track cumulative cash growth over chronological transactions."
    },
    {
        "id": 18,
        "title": "Financial Risk: Delinquent Accounts and Chargebacks",
        "question": "List all delinquent accounts or accounts with chargeback transactions, displaying total disputed amount.",
        "agent_sql": "SELECT * FROM tbl_accounts;",
        "fault": "1. Selected all accounts without transaction data.\n2. Missed join to tbl_transactions_ledger.\n3. Missed compound OR condition: acct_status_flg = 'D' OR tx_type = 'CHARGEBACK'.",
        "expected_sql": """SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
       ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
GROUP BY a.acct_id
ORDER BY total_disputed_usd DESC;""",
        "expected_explanation": "Combines account status flags with transaction ledger dispute types to quantify financial exposure."
    },
    {
        "id": 19,
        "title": "Average Storage Consumption per Tier",
        "question": "What is the average and peak daily storage in gigabytes used by accounts across each tier segment?",
        "agent_sql": "SELECT * FROM tbl_usage_telemetry;",
        "fault": "1. Dumped telemetry table in isolation.\n2. Missed join to tbl_accounts to get tier_segment.\n3. Missed GROUP BY a.tier_segment and AVG(storage_gb_used) / MAX(storage_gb_used).",
        "expected_sql": """SELECT a.tier_segment,
       ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
       ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.tier_segment
ORDER BY avg_storage_gb DESC;""",
        "expected_explanation": "Connects account tiers to daily infrastructure telemetry to benchmark storage usage."
    },
    {
        "id": 20,
        "title": "Overall Net Profit Margin",
        "question": "Calculate our overall net profit margin percentage across all settled transactions after accounting for gateway fees.",
        "agent_sql": "SELECT * FROM tbl_transactions_ledger;",
        "fault": "1. Selected raw table rows.\n2. Missed calculating mathematical ratio: (SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0 for settled charges.",
        "expected_sql": """SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
       ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
       ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
       ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;""",
        "expected_explanation": "Computes high-level financial health by dividing net settled cash by gross payment volume."
    }
]

def generate_report():
    lines = [
        "# Part A Benchmark Evaluation: 20 Tough Technical Queries",
        "",
        "> **Database:** `enterprise_nexus.sqlite` (10 tables, 1,000+ rows)",
        "> **Environment:** Local Mac M1 (Running lightweight heuristic engine)",
        "",
        "---",
        "",
        "## 📊 Executive Scorecard & Failure Analysis",
        "",
        "| Metric | Result | Root Cause Analysis |",
        "| :--- | :--- | :--- |",
        "| **Execution Success (No Crashes)** | **20 / 20 (100%)** | The SQLite sandbox successfully executed all queries without syntax errors. |",
        "| **Complex Semantic Accuracy** | **0 / 20 (0%)** | All 20 complex queries failed to produce the true analytical SQL. |",
        "",
        "### 🚨 Why All 20 Complex Queries Failed on Local Mac:",
        "On your local Mac (8GB RAM), the 16GB fine-tuned LLaMA-3 model weights are **not loaded into RAM** to prevent memory thrashing. The API fell back to `_heuristic_sql`.",
        "While heuristics work for simple queries (`SELECT * FROM tbl_customers`), **rules cannot synthesize 4-table JOINs, Window Functions, or complex GROUP BY / HAVING logic**.",
        "",
        "---",
        "",
        "## 📋 Detailed Per-Question Analysis (Q1 - Q20)",
        ""
    ]

    for item in eval_data:
        lines.append(f"### Question {item['id']}: {item['title']}")
        lines.append(f"**❓ Question Asked to Model:**")
        lines.append(f"> *\"{item['question']}\"*")
        lines.append("")
        lines.append(f"**🤖 What the Agent Actually Generated:**")
        lines.append("```sql")
        lines.append(item['agent_sql'])
        lines.append("```")
        lines.append("")
        lines.append(f"**❌ What is the Fault (The Bug / Problem):**")
        lines.append(f"{item['fault']}")
        lines.append("")
        lines.append(f"**🎯 What Was Expected (The Right Thing):**")
        lines.append("```sql")
        lines.append(item['expected_sql'])
        lines.append("```")
        lines.append(f"*{item['expected_explanation']}*")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open("BENCHMARK_PART_A_EVALUATION.md", "w") as f:
        f.write("\n".join(lines))
    print("✔ Successfully written updated BENCHMARK_PART_A_EVALUATION.md")

if __name__ == "__main__":
    generate_report()
