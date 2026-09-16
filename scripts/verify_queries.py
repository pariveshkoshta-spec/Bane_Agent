import sqlite3

def test_ground_truth_queries(db_path="enterprise_nexus.sqlite"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    queries = [
        # Q1: 3-Table Join with Aggregation (MRR by Sales Rep)
        """
        SELECT r.rep_name, r.territory, ROUND(SUM(s.mrr_cents) / 100.0, 2) AS total_active_mrr_usd
        FROM tbl_sales_reps r
        JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
        JOIN tbl_subscriptions_hist s ON aa.acct_id = s.acct_id
        WHERE s.is_cancelled = 0 AND aa.is_primary_owner = 1
        GROUP BY r.rep_id, r.rep_name
        ORDER BY total_active_mrr_usd DESC;
        """,

        # Q2: 4-Table Join (Revenue by Product Category for VIPs)
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

        # Q3: Window Function (Rank Customers by Total Spend within Each Country)
        """
        WITH customer_spend AS (
            SELECT a.country_iso3, a.client_legal_name, ROUND(SUM(t.gross_amt_usd), 2) AS total_spent
            FROM tbl_accounts a
            JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
            WHERE t.settlement_status = 'SETTLED'
            GROUP BY a.acct_id
        )
        SELECT country_iso3, client_legal_name, total_spent,
               DENSE_RANK() OVER (PARTITION BY country_iso3 ORDER BY total_spent DESC) as rank_in_country
        FROM customer_spend;
        """,

        # Q4: Conditional Aggregation & Ratio (Refund Rate by Gateway)
        """
        SELECT gateway_provider,
               COUNT(*) AS total_tx_count,
               ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
               ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
        FROM tbl_transactions_ledger
        GROUP BY gateway_provider
        ORDER BY refund_pct DESC;
        """,

        # Q5: Subquery & Filter (Accounts with Critical Unresolved Support Cases)
        """
        SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
        FROM tbl_accounts a
        JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
        WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
        ORDER BY sc.created_ts ASC;
        """
    ]

    print("Verifying sample benchmark queries against enterprise_nexus.sqlite...")
    for idx, q in enumerate(queries, 1):
        try:
            cursor.execute(q)
            rows = cursor.fetchall()
            print(f"✔ Query {idx} executed successfully! Returned {len(rows)} rows.")
        except Exception as e:
            print(f"❌ Query {idx} failed: {e}")
            raise e

    conn.close()
    print("All sample ground-truth queries verified.")

if __name__ == "__main__":
    test_ground_truth_queries()
