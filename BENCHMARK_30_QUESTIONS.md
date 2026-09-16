# Enterprise Nexus: 30 Tough & Messy Text-to-SQL Benchmark Suite

This benchmark suite evaluates the Bane Agent against **`enterprise_nexus.sqlite`**, an interconnected 10-table enterprise database featuring cryptic column names, mixed currency units (cents vs dollars), cross-table foreign keys, and status flags.

---

## Part A: 20 Tough Technical & Analytical Queries

These queries test advanced SQL capabilities including **3-to-5 table JOINs**, **Window Functions (`DENSE_RANK`, `SUM() OVER`)**, **CTEs**, **Conditional Aggregations (`SUM(CASE WHEN...)`)**, **Date formatting**, and **Ratio calculations**.

### 1. Sales Rep Active MRR (3-Table JOIN + Unit Conversion)
* **User Prompt:** `"Calculate the total active monthly recurring revenue in USD managed by each sales rep, ordered from highest to lowest."`
* **Tables Required:** `tbl_sales_reps`, `tbl_account_assignments`, `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT r.rep_name, r.territory,
         ROUND(SUM(s.mrr_cents) / 100.0, 2) AS active_mrr_usd
  FROM tbl_sales_reps r
  JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
  JOIN tbl_subscriptions_hist s ON aa.acct_id = s.acct_id
  WHERE s.cancellation_date IS NULL AND aa.is_primary_owner = 1
  GROUP BY r.rep_id, r.rep_name
  ORDER BY active_mrr_usd DESC;
  ```

### 2. VIP Product Category Revenue (4-Table JOIN)
* **User Prompt:** `"Show me total settled revenue broken down by product category generated exclusively from VIP tier accounts."`
* **Tables Required:** `tbl_accounts`, `tbl_transactions_ledger`, `tbl_order_items`, `tbl_products_catalog`
* **Expected SQL:**
  ```sql
  SELECT p.category, ROUND(SUM(oi.line_total_usd), 2) AS total_revenue_usd
  FROM tbl_accounts a
  JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
  JOIN tbl_order_items oi ON t.tx_id = oi.tx_id
  JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
  WHERE a.tier_segment = 'TIER_1_VIP' AND t.settlement_status = 'SETTLED'
  GROUP BY p.category
  ORDER BY total_revenue_usd DESC;
  ```

### 3. Customer Spend Ranking by Country (CTE + Window Function `DENSE_RANK()`)
* **User Prompt:** `"Rank all accounts within their respective country by their total settled spend volume."`
* **Tables Required:** `tbl_accounts`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
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
  ```

### 4. Gateway Refund Rate & Loss (Conditional Aggregation `CASE WHEN`)
* **User Prompt:** `"What is the refund rate percentage and total refunded amount for each payment gateway provider?"`
* **Tables Required:** `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT gateway_provider,
         COUNT(*) AS total_tx_count,
         ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
         ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
  FROM tbl_transactions_ledger
  GROUP BY gateway_provider
  ORDER BY refund_pct DESC;
  ```

### 5. Critical Unresolved Support Blockers (Multi-condition Filtering)
* **User Prompt:** `"List all client accounts currently experiencing open or investigating SEV-1 blocker support cases."`
* **Tables Required:** `tbl_accounts`, `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
  FROM tbl_accounts a
  JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
  WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
  ORDER BY sc.created_ts ASC;
  ```

### 6. Support Performance by Agent Tier (Multi-metric Aggregation)
* **User Prompt:** `"Find the average CSAT score and average response time in minutes for each support agent tier on resolved cases."`
* **Tables Required:** `tbl_support_agents`, `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT sa.tier_level,
         COUNT(sc.case_number) AS total_resolved_cases,
         ROUND(AVG(sc.csat_score), 2) AS avg_csat_score,
         ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_resp_time_mins
  FROM tbl_support_agents sa
  JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
  WHERE sc.case_status = 'RESOLVED' AND sc.csat_score IS NOT NULL
  GROUP BY sa.tier_level
  ORDER BY sa.tier_level ASC;
  ```

### 7. Top 5 Heavy Compute Consumers (Time-series Grouping)
* **User Prompt:** `"Identify the top 5 accounts with the highest cumulative compute hours consumed across all telemetry records."`
* **Tables Required:** `tbl_accounts`, `tbl_usage_telemetry`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, a.tier_segment,
         ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
         SUM(u.api_calls_count) AS total_api_calls
  FROM tbl_accounts a
  JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
  GROUP BY a.acct_id
  ORDER BY total_compute_hours DESC
  LIMIT 5;
  ```

### 8. Subscription Churn Reason Analysis (NULL Date Filtering + Sum)
* **User Prompt:** `"Break down lost monthly recurring revenue and total churned contract count by cancellation reason."`
* **Tables Required:** `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT cancellation_reason_code,
         COUNT(*) AS churned_contracts_count,
         ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
  FROM tbl_subscriptions_hist
  WHERE cancellation_date IS NOT NULL
  GROUP BY cancellation_reason_code
  ORDER BY lost_mrr_usd DESC;
  ```

### 9. Top Discounted Product Purchases (3-Table JOIN + Sorting)
* **User Prompt:** `"Show the top 3 order line items with the highest discount percentage, including product name and total line price."`
* **Tables Required:** `tbl_order_items`, `tbl_products_catalog`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT oi.line_item_id, p.product_name, oi.quantity,
         oi.discount_pct * 100 AS discount_percent,
         oi.line_total_usd, t.tx_timestamp
  FROM tbl_order_items oi
  JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
  JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
  WHERE oi.discount_pct > 0
  ORDER BY oi.discount_pct DESC, oi.line_total_usd DESC
  LIMIT 3;
  ```

### 10. Sales Rep Quota Attainment (JOIN + `HAVING` Filter)
* **User Prompt:** `"Which sales representatives have achieved or exceeded their assigned quota based on settled transactions?"`
* **Tables Required:** `tbl_sales_reps`, `tbl_account_assignments`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
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
  ```

### 11. Anomaly Detection: High 5xx Server Errors (HAVING comparison)
* **User Prompt:** `"Find all accounts that have experienced more 5xx server errors than 4xx client errors in telemetry."`
* **Tables Required:** `tbl_accounts`, `tbl_usage_telemetry`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name,
         SUM(u.error_count_5xx) AS total_5xx_errors,
         SUM(u.error_count_4xx) AS total_4xx_errors
  FROM tbl_accounts a
  JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
  GROUP BY a.acct_id
  HAVING total_5xx_errors > total_4xx_errors AND total_5xx_errors > 0
  ORDER BY total_5xx_errors DESC;
  ```

### 12. Account Growth Cohort by Month (Date Formatting `STRFTIME`)
* **User Prompt:** `"Show the number of new client accounts created per month in chronological order."`
* **Tables Required:** `tbl_accounts`
* **Expected SQL:**
  ```sql
  SELECT strftime('%Y-%m', created_at) AS signup_month,
         COUNT(*) AS new_accounts_count
  FROM tbl_accounts
  GROUP BY signup_month
  ORDER BY signup_month ASC;
  ```

### 13. Payment Gateway Settlement Stats (Min, Max, Avg Net)
* **User Prompt:** `"Calculate the average, minimum, and maximum net transaction amount for settled charges grouped by payment gateway."`
* **Tables Required:** `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT gateway_provider,
         COUNT(*) AS settled_tx_count,
         ROUND(AVG(net_amt_usd), 2) AS avg_net_usd,
         ROUND(MIN(net_amt_usd), 2) AS min_net_usd,
         ROUND(MAX(net_amt_usd), 2) AS max_net_usd
  FROM tbl_transactions_ledger
  WHERE settlement_status = 'SETTLED' AND tx_type = 'CHARGE'
  GROUP BY gateway_provider
  ORDER BY avg_net_usd DESC;
  ```

### 14. Multi-Contract Accounts (Count Filtering `HAVING COUNT > 1`)
* **User Prompt:** `"Which accounts have signed more than one subscription contract in their company history?"`
* **Tables Required:** `tbl_accounts`, `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, a.tier_segment,
         COUNT(s.sub_contract_id) AS total_contracts_count
  FROM tbl_accounts a
  JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
  GROUP BY a.acct_id
  HAVING COUNT(s.sub_contract_id) > 1
  ORDER BY total_contracts_count DESC;
  ```

### 15. Best-Selling Add-on Product (Product Category Filter + Unit Aggregation)
* **User Prompt:** `"What is the single best-selling add-on product by total units sold and how much gross sales did it generate?"`
* **Tables Required:** `tbl_order_items`, `tbl_products_catalog`
* **Expected SQL:**
  ```sql
  SELECT p.product_name, p.prod_sku, SUM(oi.quantity) AS total_units_sold,
         ROUND(SUM(oi.line_total_usd), 2) AS total_gross_sales
  FROM tbl_order_items oi
  JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
  WHERE p.category IN ('STORAGE_ADDON', 'COMPUTE_BURST')
  GROUP BY p.prod_sku
  ORDER BY total_units_sold DESC
  LIMIT 1;
  ```

### 16. Support SLA Breach Rate by Severity (Filter + Aggregate)
* **User Prompt:** `"Group cases where first response time was greater than 60 minutes by severity level, showing count and average response time."`
* **Tables Required:** `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT severity_level,
         COUNT(*) AS delayed_cases_count,
         ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
  FROM tbl_support_cases
  WHERE first_response_time_minutes > 60
  GROUP BY severity_level
  ORDER BY delayed_cases_count DESC;
  ```

### 17. Cumulative Gross Transaction Volume (Window Function `SUM() OVER`)
* **User Prompt:** `"Calculate the cumulative running total of gross transaction volume over time for settled payments."`
* **Tables Required:** `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT tx_id, tx_timestamp, gross_amt_usd,
         ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
  FROM tbl_transactions_ledger
  WHERE settlement_status = 'SETTLED'
  LIMIT 10;
  ```

### 18. Financial Risk: Delinquent Accounts and Chargebacks (`OR` Logic + `ABS`)
* **User Prompt:** `"List all delinquent accounts or accounts with chargeback transactions, displaying total disputed amount."`
* **Tables Required:** `tbl_accounts`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
         ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
  FROM tbl_accounts a
  JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
  WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
  GROUP BY a.acct_id
  ORDER BY total_disputed_usd DESC;
  ```

### 19. Average Storage Consumption per Tier (Grouped Analytics)
* **User Prompt:** `"What is the average and peak daily storage in gigabytes used by accounts across each tier segment?"`
* **Tables Required:** `tbl_accounts`, `tbl_usage_telemetry`
* **Expected SQL:**
  ```sql
  SELECT a.tier_segment,
         ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
         ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
  FROM tbl_accounts a
  JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
  GROUP BY a.tier_segment
  ORDER BY avg_storage_gb DESC;
  ```

### 20. Overall Net Profit Margin (Gross vs Fees Math)
* **User Prompt:** `"Calculate our overall net profit margin percentage across all settled transactions after accounting for gateway fees."`
* **Tables Required:** `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
         ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
         ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
         ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
  FROM tbl_transactions_ledger
  WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;
  ```

---

## Part B: 10 Messy / Non-Tech Stakeholder Queries

These questions mimic real business conversations: colloquial slang, vague terms, missing technical jargon, and complex implicit business logic.

### 21. Big Whales Who Cancelled
* **Non-Tech Prompt:** `"Who are our biggest whales that cancelled on us and what excuse did they give?"`
* **Semantic Translation:** Filter accounts in VIP or Enterprise tier with non-null `cancellation_date`, ordered by `mrr_cents` descending.
* **Tables Required:** `tbl_accounts`, `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, s.plan_code, ROUND(s.mrr_cents / 100.0, 2) AS lost_mrr_usd,
         s.cancellation_date, s.cancellation_reason_code
  FROM tbl_accounts a
  JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
  WHERE s.cancellation_date IS NOT NULL AND a.tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')
  ORDER BY s.mrr_cents DESC;
  ```

### 22. Top Cash Producer Sales Rep
* **Non-Tech Prompt:** `"Which sales rep is crushing it the most this year in terms of actual settled cash, not just contracts?"`
* **Semantic Translation:** Primary rep assignment with maximum sum of `net_amt_usd` where `settlement_status = 'SETTLED'`.
* **Tables Required:** `tbl_sales_reps`, `tbl_account_assignments`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT r.rep_name, r.territory, ROUND(SUM(t.net_amt_usd), 2) AS total_cash_settled_usd
  FROM tbl_sales_reps r
  JOIN tbl_account_assignments aa ON r.rep_id = aa.rep_id
  JOIN tbl_transactions_ledger t ON aa.acct_id = t.acct_id
  WHERE t.settlement_status = 'SETTLED' AND aa.is_primary_owner = 1
  GROUP BY r.rep_id
  ORDER BY total_cash_settled_usd DESC
  LIMIT 1;
  ```

### 23. Bleeding Accounts (More Refunds Than Charges)
* **Non-Tech Prompt:** `"Show me accounts that are bleeding us money with more refunds than actual charges."`
* **Semantic Translation:** Accounts where count of `REFUND` transactions exceeds count of `CHARGE` transactions.
* **Tables Required:** `tbl_accounts`, `tbl_transactions_ledger`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name,
         SUM(CASE WHEN t.tx_type = 'REFUND' THEN 1 ELSE 0 END) AS refund_count,
         SUM(CASE WHEN t.tx_type = 'CHARGE' THEN 1 ELSE 0 END) AS charge_count,
         ROUND(SUM(t.gross_amt_usd), 2) AS net_balance_usd
  FROM tbl_accounts a
  JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
  GROUP BY a.acct_id
  HAVING refund_count > charge_count;
  ```

### 24. VIP Clients with Poor Support Reviews
* **Non-Tech Prompt:** `"Find the VIP clients who had terrible support experience lately with really bad review scores."`
* **Semantic Translation:** Accounts with `tier_segment = 'TIER_1_VIP'` joined to support cases with `csat_score <= 2`.
* **Tables Required:** `tbl_accounts`, `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, sc.case_number, sc.csat_score, sc.severity_level, sc.created_ts
  FROM tbl_accounts a
  JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
  WHERE a.tier_segment = 'TIER_1_VIP' AND sc.csat_score <= 2
  ORDER BY sc.csat_score ASC, sc.created_ts DESC;
  ```

### 25. True Total MRR in Plain Dollars
* **Non-Tech Prompt:** `"What's our total monthly recurring revenue right now in plain dollars, not pennies?"`
* **Semantic Translation:** Sum `mrr_cents / 100.0` for all subscriptions where `cancellation_date IS NULL`.
* **Tables Required:** `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT ROUND(SUM(mrr_cents) / 100.0, 2) AS total_active_mrr_usd
  FROM tbl_subscriptions_hist
  WHERE cancellation_date IS NULL;
  ```

### 26. Silent Sufferers (Server Errors with Zero Filed Tickets)
* **Non-Tech Prompt:** `"Are there any accounts getting hammered with server errors but nobody filed a ticket for them?"`
* **Semantic Translation:** Accounts with telemetry `error_count_5xx > 0` joined with `LEFT JOIN` on support cases where `case_number IS NULL`.
* **Tables Required:** `tbl_accounts`, `tbl_usage_telemetry`, `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, SUM(u.error_count_5xx) AS total_server_errors
  FROM tbl_accounts a
  JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
  LEFT JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
  WHERE sc.case_number IS NULL
  GROUP BY a.acct_id
  HAVING total_server_errors > 0
  ORDER BY total_server_errors DESC;
  ```

### 27. Add-ons Bundled with Custom Enterprise Plans
* **Non-Tech Prompt:** `"Which products are driving the most money when bundled with our big enterprise plans?"`
* **Semantic Translation:** Total line items gross sales joined across products, transactions, and subscriptions with `plan_code = 'PLAN_ENT_CUSTOM'`.
* **Tables Required:** `tbl_products_catalog`, `tbl_order_items`, `tbl_transactions_ledger`, `tbl_subscriptions_hist`
* **Expected SQL:**
  ```sql
  SELECT p.product_name, p.category, ROUND(SUM(oi.line_total_usd), 2) AS gross_sales_usd
  FROM tbl_order_items oi
  JOIN tbl_products_catalog p ON oi.prod_sku = p.prod_sku
  JOIN tbl_transactions_ledger t ON oi.tx_id = t.tx_id
  JOIN tbl_subscriptions_hist s ON t.sub_contract_id = s.sub_contract_id
  WHERE s.plan_code = 'PLAN_ENT_CUSTOM'
  GROUP BY p.prod_sku
  ORDER BY gross_sales_usd DESC;
  ```

### 28. Delinquent European Clients
* **Non-Tech Prompt:** `"Give me a list of folks in Europe who haven't paid their bills and are suspended."`
* **Semantic Translation:** European country codes (`DEU`, `GBR`, `FRA`) with account status flag in `('S', 'D')`.
* **Tables Required:** `tbl_accounts`
* **Expected SQL:**
  ```sql
  SELECT client_legal_name, contact_person, contact_email, country_iso3, acct_status_flg
  FROM tbl_accounts
  WHERE country_iso3 IN ('DEU', 'GBR', 'FRA') AND acct_status_flg IN ('S', 'D');
  ```

### 29. Slowest Agent on Emergency Outages
* **Non-Tech Prompt:** `"Who is our slowest support agent to reply when a customer has a critical emergency blocker?"`
* **Semantic Translation:** Agent with highest average `first_response_time_minutes` on cases where `severity_level = 'SEV_1_BLOCKER'`.
* **Tables Required:** `tbl_support_agents`, `tbl_support_cases`
* **Expected SQL:**
  ```sql
  SELECT sa.agent_full_name, sa.region,
         ROUND(AVG(sc.first_response_time_minutes), 1) AS avg_blocker_response_mins,
         COUNT(*) AS blocker_cases_handled
  FROM tbl_support_agents sa
  JOIN tbl_support_cases sc ON sa.agent_id = sc.assigned_agent_id
  WHERE sc.severity_level = 'SEV_1_BLOCKER'
  GROUP BY sa.agent_id
  ORDER BY avg_blocker_response_mins DESC
  LIMIT 1;
  ```

### 30. SMB Resource Hogs (Cheap Tier with High Compute)
* **Non-Tech Prompt:** `"Which accounts used an insane amount of compute hours last week but are only on our cheap starter tier?"`
* **Semantic Translation:** Filter `tier_segment = 'TIER_4_SMB'` ordered by sum of `compute_hours_consumed` descending.
* **Tables Required:** `tbl_accounts`, `tbl_usage_telemetry`
* **Expected SQL:**
  ```sql
  SELECT a.client_legal_name, a.tier_segment,
         ROUND(SUM(u.compute_hours_consumed), 2) AS total_compute_hours,
         SUM(u.api_calls_count) AS total_api_calls
  FROM tbl_accounts a
  JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
  WHERE a.tier_segment = 'TIER_4_SMB'
  GROUP BY a.acct_id
  ORDER BY total_compute_hours DESC
  LIMIT 5;
  ```
