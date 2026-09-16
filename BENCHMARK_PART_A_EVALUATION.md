# Part A Benchmark Evaluation: 20 Tough Technical Queries

> Evaluation conducted against **`enterprise_nexus.sqlite`**.
> This document records the Agent's generated SQL, execution outcome, and a detailed gap analysis vs Ground-Truth SQL for manual review.

---

## Question 1: Sales Rep Active MRR (3-Table JOIN + Cents Conversion)
**Prompt:** *"Calculate the total active monthly recurring revenue in USD managed by each sales rep, ordered from highest to lowest."*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_subscriptions_hist ORDER BY 1 DESC LIMIT 5;
```
* **Execution Status:** `SUCCESS` (5 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 8 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Schema Retrieval (FAISS):** Context missed table(s): `tbl_account_assignments`.
- **Missing Multi-Table JOIN:** Required 3-table JOIN across `tbl_sales_reps, tbl_account_assignments, tbl_subscriptions_hist`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.
- **Unit Mismatch:** Did not convert `mrr_cents` to USD dollars (`/ 100.0`).

---

## Question 2: VIP Product Category Revenue (4-Table JOIN)
**Prompt:** *"Show me total settled revenue broken down by product category generated exclusively from VIP tier accounts."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_order_items;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 3 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 4-table JOIN across `tbl_accounts, tbl_transactions_ledger, tbl_order_items, tbl_products_catalog`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 3: Customer Spend Ranking by Country (Window Function DENSE_RANK)
**Prompt:** *"Rank all accounts within their respective country by their total settled spend volume."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_account_assignments;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 47 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_transactions_ledger`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.
- **Missing Window Function:** Expected Window function (`DENSE_RANK() OVER` or `SUM() OVER`), but generated query used standard SELECT.

---

## Question 4: Gateway Refund Rate & Loss (Conditional Aggregation CASE WHEN)
**Prompt:** *"What is the refund rate percentage and total refunded amount for each payment gateway provider?"*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_transactions_ledger;
```
* **Execution Status:** `SUCCESS` (167 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT gateway_provider,
       COUNT(*) AS total_tx_count,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
FROM tbl_transactions_ledger
GROUP BY gateway_provider
ORDER BY refund_pct DESC;
```
* **Expected Result:** 4 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.
- **Missing Conditional Logic:** Expected `CASE WHEN` conditional aggregation.

---

## Question 5: Critical Unresolved Support Blockers (Filter & Multi-column)
**Prompt:** *"List all client accounts currently experiencing open or investigating SEV-1 blocker support cases."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_support_cases;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
ORDER BY sc.created_ts ASC;
```
* **Expected Result:** 4 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_support_cases`, but generated query queried only a single table.

---

## Question 6: Support Performance by Agent Tier (Multi-metric Aggregation)
**Prompt:** *"Find the average CSAT score and average response time in minutes for each support agent tier on resolved cases."*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_support_cases LIMIT 20;
```
* **Execution Status:** `SUCCESS` (20 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 3 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_support_agents, tbl_support_cases`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 7: Top 5 Heavy Compute Consumers (Time-series Grouping)
**Prompt:** *"Identify the top 5 accounts with the highest cumulative compute hours consumed across all telemetry records."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 5 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_usage_telemetry`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 8: Subscription Churn Reason Analysis (NULL Date Filtering)
**Prompt:** *"Break down lost monthly recurring revenue and total churned contract count by cancellation reason."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT cancellation_reason_code,
       COUNT(*) AS churned_contracts_count,
       ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NOT NULL
GROUP BY cancellation_reason_code
ORDER BY lost_mrr_usd DESC;
```
* **Expected Result:** 5 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.
- **Unit Mismatch:** Did not convert `mrr_cents` to USD dollars (`/ 100.0`).

---

## Question 9: Top Discounted Product Purchases (3-Table JOIN + Sorting)
**Prompt:** *"Show the top 3 order line items with the highest discount percentage, including product name and total line price."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_order_items;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 3 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 3-table JOIN across `tbl_order_items, tbl_products_catalog, tbl_transactions_ledger`, but generated query queried only a single table.

---

## Question 10: Sales Rep Quota Attainment (JOIN + HAVING Filter)
**Prompt:** *"Which sales representatives have achieved or exceeded their assigned quota based on settled transactions?"*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_sales_reps LIMIT 20;
```
* **Execution Status:** `SUCCESS` (10 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 0 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 3-table JOIN across `tbl_sales_reps, tbl_account_assignments, tbl_transactions_ledger`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 11: Anomaly Detection: High 5xx Server Errors (HAVING comparison)
**Prompt:** *"Find all accounts that have experienced more 5xx server errors than 4xx client errors in telemetry."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 0 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_usage_telemetry`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 12: Account Growth Cohort by Month (STRFTIME)
**Prompt:** *"Show the number of new client accounts created per month in chronological order."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT strftime('%Y-%m', created_at) AS signup_month,
       COUNT(*) AS new_accounts_count
FROM tbl_accounts
GROUP BY signup_month
ORDER BY signup_month ASC;
```
* **Expected Result:** 15 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 13: Payment Gateway Settlement Stats (Min, Max, Avg Net)
**Prompt:** *"Calculate the average, minimum, and maximum net transaction amount for settled charges grouped by payment gateway."*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_transactions_ledger LIMIT 20;
```
* **Execution Status:** `SUCCESS` (20 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 4 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 14: Multi-Contract Accounts (Count Filtering HAVING COUNT > 1)
**Prompt:** *"Which accounts have signed more than one subscription contract in their company history?"*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT a.client_legal_name, a.tier_segment,
       COUNT(s.sub_contract_id) AS total_contracts_count
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
GROUP BY a.acct_id
HAVING COUNT(s.sub_contract_id) > 1
ORDER BY total_contracts_count DESC;
```
* **Expected Result:** 18 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_subscriptions_hist`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 15: Best-Selling Add-on Product (Product Category Filter + Unit Aggregation)
**Prompt:** *"What is the single best-selling add-on product by total units sold and how much gross sales did it generate?"*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_products_catalog;
```
* **Execution Status:** `SUCCESS` (8 rows returned)

### 🎯 Ground-Truth Target SQL:
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
* **Expected Result:** 1 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_order_items, tbl_products_catalog`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 16: Support SLA Breach Rate by Severity (Filter + Aggregate)
**Prompt:** *"Group cases where first response time was greater than 60 minutes by severity level, showing count and average response time."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_support_cases;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT severity_level,
       COUNT(*) AS delayed_cases_count,
       ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
FROM tbl_support_cases
WHERE first_response_time_minutes > 60
GROUP BY severity_level
ORDER BY delayed_cases_count DESC;
```
* **Expected Result:** 4 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 17: Cumulative Gross Transaction Volume (Window Function SUM() OVER)
**Prompt:** *"Calculate the cumulative running total of gross transaction volume over time for settled payments."*

### 🤖 Agent Generated SQL:
```sql
SELECT * FROM tbl_subscriptions_hist;
```
* **Execution Status:** `SUCCESS` (68 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT tx_id, tx_timestamp, gross_amt_usd,
       ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED'
LIMIT 10;
```
* **Expected Result:** 10 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Window Function:** Expected Window function (`DENSE_RANK() OVER` or `SUM() OVER`), but generated query used standard SELECT.

---

## Question 18: Financial Risk: Delinquent Accounts and Chargebacks (OR Logic + ABS)
**Prompt:** *"List all delinquent accounts or accounts with chargeback transactions, displaying total disputed amount."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_transactions_ledger;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
       ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
GROUP BY a.acct_id
ORDER BY total_disputed_usd DESC;
```
* **Expected Result:** 22 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_transactions_ledger`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 19: Average Storage Consumption per Tier (Grouped Analytics)
**Prompt:** *"What is the average and peak daily storage in gigabytes used by accounts across each tier segment?"*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT a.tier_segment,
       ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
       ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.tier_segment
ORDER BY avg_storage_gb DESC;
```
* **Expected Result:** 4 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- **Missing Multi-Table JOIN:** Required 2-table JOIN across `tbl_accounts, tbl_usage_telemetry`, but generated query queried only a single table.
- **Missing Aggregation:** Expected `GROUP BY` grouping, but generated query did not group rows.

---

## Question 20: Overall Net Profit Margin (Gross vs Fees Math)
**Prompt:** *"Calculate our overall net profit margin percentage across all settled transactions after accounting for gateway fees."*

### 🤖 Agent Generated SQL:
```sql
SELECT COUNT(*) AS total_count FROM tbl_transactions_ledger;
```
* **Execution Status:** `SUCCESS` (1 rows returned)

### 🎯 Ground-Truth Target SQL:
```sql
SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
       ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
       ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
       ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;
```
* **Expected Result:** 1 rows returned from ground-truth query.

### 🔍 Problems & Gap Analysis for Review:
- ✔ **Query Executed Cleanly.** Schema and basic intent aligned.

---
