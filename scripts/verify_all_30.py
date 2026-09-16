import sqlite3

benchmark_queries = [
    # --- PART A: 20 TOUGH TECHNICAL & ANALYTICAL QUERIES ---

    # 1. Total Active Monthly Recurring Revenue (USD) managed by each Sales Rep
    """
    SELECT r.rep_name, r.territory,
           ROUND(SUM(s.mrr_cents) / 100.0, 2) AS active_mrr_usd
    FROM tbl_sales_reps r
    JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
    JOIN tbl_subscriptions_hist s ON aa.acct_id = s.acct_id
    WHERE s.cancellation_date IS NULL AND aa.is_primary_owner = 1
    GROUP BY r.rep_id, r.rep_name
    ORDER BY active_mrr_usd DESC;
    """,

    # 2. Revenue by Product Category from VIP accounts with settled transactions
    """
    SELECT p.category, ROUND(SUM(oi.line_total_usd), 2) AS total_revenue_usd
    FROM tbl_accounts a
    JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
    JOIN tbl_order_items oi ON t.tx_id = oi.tx_id
    JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
    WHERE a.tier_segment = 'TIER_1_VIP' AND t.settlement_status = 'SETTLED'
    GROUP BY p.category
    ORDER BY total_revenue_usd DESC;
    """,

    # 3. Rank accounts within each country by their total gross payment volume
    """
    WITH customer_spend AS (
        SELECT a.country_iso3, a.client_legal_name, ROUND(SUM(t.gross_amt_usd), 2) AS total_spent
        FROM tbl_accounts a
        JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
        WHERE t.settlement_status = 'SETTLED'
        GROUP BY a.acct_id
    )
    SELECT country_iso3, client_legal_name, total_spent,
           DENSE_RANK() OVER (PARTITION BY country_iso3 ORDER BY total_spent DESC) AS country_rank
    FROM customer_spend
    ORDER BY country_iso3, country_rank;
    """,

    # 4. Refund rate percentage and total refunded amount by payment gateway
    """
    SELECT gateway_provider,
           COUNT(*) AS total_tx_count,
           ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
           ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
    FROM tbl_transactions_ledger
    GROUP BY gateway_provider
    ORDER BY refund_pct DESC;
    """,

    # 5. Accounts with active blocker (SEV-1) support cases that are still unresolved
    """
    SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
    FROM tbl_accounts a
    JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
    WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
    ORDER BY sc.created_ts ASC;
    """,

    # 6. Average CSAT score and resolved case count for each support agent tier
    """
    SELECT sa.tier_level,
           COUNT(sc.case_number) AS total_resolved_cases,
           ROUND(AVG(sc.csat_score), 2) AS avg_csat_score,
           ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_resp_time_mins
    FROM tbl_support_agents sa
    JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
    WHERE sc.case_status = 'RESOLVED' AND sc.csat_score IS NOT NULL
    GROUP BY sa.tier_level
    ORDER BY sa.tier_level ASC;
    """,

    # 7. Top 5 accounts with the highest total compute hours consumed across all telemetry dates
    """
    SELECT a.client_legal_name, a.tier_segment,
           ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
           SUM(u.api_calls_count) AS total_api_calls
    FROM tbl_accounts a
    JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
    GROUP BY a.acct_id
    ORDER BY total_compute_hours DESC
    LIMIT 5;
    """,

    # 8. Subscription churn breakdown: Count and lost MRR (USD) by cancellation reason
    """
    SELECT cancellation_reason_code,
           COUNT(*) AS churned_contracts_count,
           ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
    FROM tbl_subscriptions_hist
    WHERE cancellation_date IS NOT NULL
    GROUP BY cancellation_reason_code
    ORDER BY lost_mrr_usd DESC;
    """,

    # 9. Top 3 highest discount orders with product name, original price, and final price
    """
    SELECT oi.line_item_id, p.product_name, oi.quantity,
           oi.discount_pct * 100 AS discount_percent,
           oi.line_total_usd, t.tx_timestamp
    FROM tbl_order_items oi
    JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
    JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
    WHERE oi.discount_pct > 0
    ORDER BY oi.discount_pct DESC, oi.line_total_usd DESC
    LIMIT 3;
    """,

    # 10. Sales representatives who have exceeded their quota based on primary account transactions
    """
    SELECT r.rep_name, r.quota_amount_usd,
           ROUND(SUM(t.net_amt_usd), 2) AS total_net_settled_usd,
           ROUND(SUM(t.net_amt_usd) * 100.0 / r.quota_amount_usd, 2) AS quota_attainment_pct
    FROM tbl_sales_reps r
    JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
    JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
    WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
    GROUP BY r.rep_id
    HAVING total_net_settled_usd >= r.quota_amount_usd
    ORDER BY quota_attainment_pct DESC;
    """,

    # 11. Accounts having higher 5xx server error rate than 4xx client errors
    """
    SELECT a.client_legal_name,
           SUM(u.error_count_5xx) AS total_5xx_errors,
           SUM(u.error_count_4xx) AS total_4xx_errors
    FROM tbl_accounts a
    JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
    GROUP BY a.acct_id
    HAVING total_5xx_errors > total_4xx_errors AND total_5xx_errors > 0
    ORDER BY total_5xx_errors DESC;
    """,

    # 12. Monthly active accounts cohort: count of accounts created per month
    """
    SELECT strftime('%Y-%m', created_at) AS signup_month,
           COUNT(*) AS new_accounts_count
    FROM tbl_accounts
    GROUP BY signup_month
    ORDER BY signup_month ASC;
    """,

    # 13. Average transaction net value partitioned by payment gateway provider
    """
    SELECT gateway_provider,
           COUNT(*) AS settled_tx_count,
           ROUND(AVG(net_amt_usd), 2) AS avg_net_usd,
           ROUND(MIN(net_amt_usd), 2) AS min_net_usd,
           ROUND(MAX(net_amt_usd), 2) AS max_net_usd
    FROM tbl_transactions_ledger
    WHERE settlement_status = 'SETTLED' AND tx_type = 'CHARGE'
    GROUP BY gateway_provider
    ORDER BY avg_net_usd DESC;
    """,

    # 14. Accounts that have multiple subscription contracts in history
    """
    SELECT a.client_legal_name, a.tier_segment,
           COUNT(s.sub_contract_id) AS total_contracts_count
    FROM tbl_accounts a
    JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
    GROUP BY a.acct_id
    HAVING COUNT(s.sub_contract_id) > 1
    ORDER BY total_contracts_count DESC;
    """,

    # 15. The single most popular add-on product by total units sold
    """
    SELECT p.product_name, p.prod_sku, SUM(oi.quantity) AS total_units_sold,
           ROUND(SUM(oi.line_total_usd), 2) AS total_gross_sales
    FROM tbl_order_items oi
    JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
    WHERE p.category IN ('STORAGE_ADDON', 'COMPUTE_BURST')
    GROUP BY p.prod_sku
    ORDER BY total_units_sold DESC
    LIMIT 1;
    """,

    # 16. Support cases where first response took longer than 60 minutes, grouped by severity
    """
    SELECT severity_level,
           COUNT(*) AS delayed_cases_count,
           ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
    FROM tbl_support_cases
    WHERE first_response_time_minutes > 60
    GROUP BY severity_level
    ORDER BY delayed_cases_count DESC;
    """,

    # 17. Cumulative running total of gross transaction volume over time
    """
    SELECT tx_id, tx_timestamp, gross_amt_usd,
           ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
    FROM tbl_transactions_ledger
    WHERE settlement_status = 'SETTLED'
    LIMIT 10;
    """,

    # 18. Delinquent accounts with their total unpaid or chargebacked transaction amount
    """
    SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
           ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
    FROM tbl_accounts a
    JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
    WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
    GROUP BY a.acct_id
    ORDER BY total_disputed_usd DESC;
    """,

    # 19. Average daily storage consumption (GB) per tier segment
    """
    SELECT a.tier_segment,
           ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
           ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
    FROM tbl_accounts a
    JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
    GROUP BY a.tier_segment
    ORDER BY avg_storage_gb DESC;
    """,

    # 20. Net profit margin across transactions after gateway fees
    """
    SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
           ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
           ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
           ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
    FROM tbl_transactions_ledger
    WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;
    """,

    # --- PART B: 10 MESSY / NON-TECH STAKEHOLDER QUERIES ---

    # 21. "Who are our biggest whales that cancelled on us and what excuse did they give?"
    """
    SELECT a.client_legal_name, s.plan_code, ROUND(s.mrr_cents / 100.0, 2) AS lost_mrr_usd,
           s.cancellation_date, s.cancellation_reason_code
    FROM tbl_accounts a
    JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
    WHERE s.cancellation_date IS NOT NULL AND a.tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')
    ORDER BY s.mrr_cents DESC;
    """,

    # 22. "Which sales rep is crushing it the most this year in terms of actual settled cash, not just contracts?"
    """
    SELECT r.rep_name, r.territory, ROUND(SUM(t.net_amt_usd), 2) AS total_cash_settled_usd
    FROM tbl_sales_reps r
    JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
    JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
    WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
    GROUP BY r.rep_id
    ORDER BY total_cash_settled_usd DESC
    LIMIT 1;
    """,

    # 23. "Show me accounts that are bleeding us money with more refunds than actual charges."
    """
    SELECT a.client_legal_name,
           SUM(CASE WHEN t.tx_type = 'REFUND' THEN 1 ELSE 0 END) AS refund_count,
           SUM(CASE WHEN t.tx_type = 'CHARGE' THEN 1 ELSE 0 END) AS charge_count,
           ROUND(SUM(t.gross_amt_usd), 2) AS net_balance_usd
    FROM tbl_accounts a
    JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
    GROUP BY a.acct_id
    HAVING refund_count > charge_count;
    """,

    # 24. "Find the VIP clients who had terrible support experience lately with really bad review scores."
    """
    SELECT a.client_legal_name, sc.case_number, sc.csat_score, sc.severity_level, sc.created_ts
    FROM tbl_accounts a
    JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
    WHERE a.tier_segment = 'TIER_1_VIP' AND sc.csat_score <= 2
    ORDER BY sc.csat_score ASC, sc.created_ts DESC;
    """,

    # 25. "What's our total monthly recurring revenue right now in plain dollars, not pennies?"
    """
    SELECT ROUND(SUM(mrr_cents) / 100.0, 2) AS total_active_mrr_usd
    FROM tbl_subscriptions_hist
    WHERE cancellation_date IS NULL;
    """,

    # 26. "Are there any accounts getting hammered with server errors but nobody filed a ticket for them?"
    """
    SELECT a.client_legal_name, SUM(u.error_count_5xx) AS total_server_errors
    FROM tbl_accounts a
    JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
    LEFT JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
    WHERE sc.case_number IS NULL
    GROUP BY a.acct_id
    HAVING total_server_errors > 0
    ORDER BY total_server_errors DESC;
    """,

    # 27. "Which products are driving the most money when bundled with our big enterprise plans?"
    """
    SELECT p.product_name, p.category, ROUND(SUM(oi.line_total_usd), 2) AS gross_sales_usd
    FROM tbl_order_items oi
    JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
    JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
    JOIN tbl_subscriptions_hist s ON t.sub_contract_id = s.sub_contract_id
    WHERE s.plan_code = 'PLAN_ENT_CUSTOM'
    GROUP BY p.prod_sku
    ORDER BY gross_sales_usd DESC;
    """,

    # 28. "Give me a list of folks in Europe who haven't paid their bills and are suspended."
    """
    SELECT client_legal_name, contact_person, contact_email, country_iso3, acct_status_flg
    FROM tbl_accounts
    WHERE country_iso3 IN ('DEU', 'GBR', 'FRA') AND acct_status_flg IN ('S', 'D');
    """,

    # 29. "Who is our slowest support agent to reply when a customer has a critical emergency blocker?"
    """
    SELECT sa.agent_full_name, sa.region,
           ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_blocker_response_mins,
           COUNT(*) AS blocker_cases_handled
    FROM tbl_support_agents sa
    JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
    WHERE sc.severity_level = 'SEV_1_BLOCKER'
    GROUP BY sa.agent_id
    ORDER BY avg_blocker_response_mins DESC
    LIMIT 1;
    """,

    # 30. "Which accounts used an insane amount of compute hours last week but are only on our cheap starter tier?"
    """
    SELECT a.client_legal_name, a.tier_segment,
           ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
           SUM(u.api_calls_count) AS total_api_calls
    FROM tbl_accounts a
    JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
    WHERE a.tier_segment = 'TIER_4_SMB'
    GROUP BY a.acct_id
    ORDER BY total_compute_hours DESC
    LIMIT 5;
    """
]

def verify_all_30():
    conn = sqlite3.connect("enterprise_nexus.sqlite")
    cursor = conn.cursor()
    success_count = 0

    print("Verifying all 30 Benchmark Queries against enterprise_nexus.sqlite...\n")
    for i, q in enumerate(benchmark_queries, 1):
        try:
            cursor.execute(q)
            rows = cursor.fetchall()
            print(f"✔ Query {i:02d}: Executed successfully ({len(rows)} rows returned)")
            success_count += 1
        except Exception as e:
            print(f"❌ Query {i:02d}: FAILED -> {e}\nQuery:\n{q}")

    conn.close()
    print(f"\n==========================================")
    print(f"Result: {success_count}/{len(benchmark_queries)} queries executed flawlessly.")

if __name__ == "__main__":
    verify_all_30()
