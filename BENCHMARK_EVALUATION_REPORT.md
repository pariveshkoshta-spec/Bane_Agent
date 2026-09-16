# Complete Benchmark Evaluation Report: 30 Tough & Messy Queries

> **Target Database:** `enterprise_nexus.sqlite` (10 interconnected tables, 1,000+ rows)
> **API Server Endpoint Tested:** `https://miniature-space-adventure-pj4vjrr6x6p7c7wgv-8000.app.github.dev/` (GitHub Codespaces Cloud Deployment)
> **Inference Engine Observed:** Fallback Heuristic Generator (LoRA PyTorch weights inactive due to CPU VM hardware & missing CUDA/peft)

---

## 📊 Executive Scorecard & Gap Analysis

| Evaluation Section | Total Queries | Syntax Execution Pass | Complex Semantic Pass | Main Failure Reason |
| :--- | :---: | :---: | :---: | :--- |
| **Part A: Technical & Analytical** | 20 | 20/20 (100%) | 0/20 (0%) | Heuristic engine cannot generate 4-table JOINs, Window functions (`DENSE_RANK`), or `GROUP BY ... HAVING`. |
| **Part B: Messy / Non-Tech Slang** | 10 | 10/10 (100%) | 0/10 (0%) | Heuristics cannot decode conversational slang (*'whales'*, *'bleeding money'*, *'crushing it'*). |
| **TOTAL OVERALL** | **30** | **30/30 (100%)** | **0/30 (0%)** | Requires neural LLM inference & schema linking rather than static Python rules. |

---

## 🚨 Key Findings: Why Every Complex Query Failed on Codespaces
1. **The Fallback Engine Executed Instead of the Neural Weights:** When the Codespaces API started, `/load_model` reported `No module named 'peft'` because `peft` wasn't installed, and Codespaces VMs are standard 2/4-core CPU machines without NVIDIA CUDA GPUs. 4-bit `bitsandbytes` quantization strictly requires CUDA. As a result, the API gracefully fell back to `_heuristic_sql`.
2. **The Slang & Semantic Blindspot (Part B):** Non-technical users ask: *'Who are our biggest whales that cancelled?'*. A rule engine looks for a column named `whale`. A fine-tuned LLM understands that *'whales'* refers to `tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')` and *'cancelled'* means `cancellation_date IS NOT NULL`.
3. **The Multi-Table Bridge Problem:** Questions requiring 3 to 4 tables failed because the RAG engine only retrieved the primary tables and missed intermediate junction tables (e.g. `tbl_account_assignments`).

---

# Part A: 20 Tough Technical Queries

### Question 1: Sales Rep Active MRR
**❓ Question Asked to Model:**
> *"Calculate the total active monthly recurring revenue in USD managed by each sales rep, ordered from highest to lowest."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_subscriptions_hist ORDER BY 1 DESC LIMIT 5;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Queried tbl_subscriptions_hist in isolation, completely missing tbl_sales_reps and the junction table tbl_account_assignments.
2. Did not group by sales rep (GROUP BY r.rep_id).
3. Missed the business logic of converting mrr_cents to USD (requires dividing by 100.0).
4. Failed to filter for active contracts only (cancellation_date IS NULL).

**🎯 What Was Expected (The Right Thing):**
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
*Requires a 3-table join traversing reps -> account assignments -> active subscriptions, summing mrr_cents divided by 100 to produce actual dollar amounts per sales rep.*

---

### Question 2: VIP Product Category Revenue
**❓ Question Asked to Model:**
> *"Show me total settled revenue broken down by product category generated exclusively from VIP tier accounts."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_order_items;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned a single count of order items instead of grouping revenue by product category.
2. Missed the 4-table join required: tbl_accounts -> tbl_transactions_ledger -> tbl_order_items -> tbl_products_catalog.
3. Completely omitted the filter for VIP accounts (tier_segment = 'TIER_1_VIP') and settled status (settlement_status = 'SETTLED').

**🎯 What Was Expected (The Right Thing):**
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
*Links 4 tables to trace product categories purchased by VIP accounts that resulted in settled ledger transactions.*

---

### Question 3: Customer Spend Ranking by Country
**❓ Question Asked to Model:**
> *"Rank all accounts within their respective country by their total settled spend volume."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_account_assignments;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Hit the wrong table (tbl_account_assignments) instead of tbl_accounts and tbl_transactions_ledger.
2. Has no concept of analytical Window Functions (DENSE_RANK() OVER (PARTITION BY ...)).
3. Did not group customer spend or calculate rank.

**🎯 What Was Expected (The Right Thing):**
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
*Requires an initial CTE to aggregate spend per account, followed by a window function partitioning by country to rank accounts from highest to lowest spend.*

---

### Question 4: Gateway Refund Rate & Loss
**❓ Question Asked to Model:**
> *"What is the refund rate percentage and total refunded amount for each payment gateway provider?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_transactions_ledger;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Dumped the raw transaction ledger without grouping.
2. Missed GROUP BY gateway_provider.
3. Missing conditional aggregation (SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END)) to calculate refund percentage vs total transactions.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT gateway_provider,
       COUNT(*) AS total_tx_count,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS refund_pct,
       ROUND(SUM(CASE WHEN tx_type = 'REFUND' THEN ABS(gross_amt_usd) ELSE 0 END), 2) AS total_refunded_usd
FROM tbl_transactions_ledger
GROUP BY gateway_provider
ORDER BY refund_pct DESC;
```
*Uses conditional CASE WHEN to count refunds separately from total transactions, computing both the percentage rate and absolute loss per provider.*

---

### Question 5: Critical Unresolved Support Blockers
**❓ Question Asked to Model:**
> *"List all client accounts currently experiencing open or investigating SEV-1 blocker support cases."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_support_cases;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned an aggregate COUNT instead of listing the actual accounts.
2. Did not join tbl_accounts to get client legal name, contact email, and account tier.
3. Failed to filter for severity_level = 'SEV_1_BLOCKER' and active status in ('OPEN', 'INVESTIGATING').

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.client_legal_name, a.contact_email, a.tier_segment, sc.case_number, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE sc.severity_level = 'SEV_1_BLOCKER' AND sc.case_status IN ('OPEN', 'INVESTIGATING')
ORDER BY sc.created_ts ASC;
```
*Joins accounts to support cases with exact filters on severity and status to highlight active production blockers with client contact details.*

---

### Question 6: Support Performance by Agent Tier
**❓ Question Asked to Model:**
> *"Find the average CSAT score and average response time in minutes for each support agent tier on resolved cases."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_support_cases LIMIT 20;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Simple select on cases table with limit 20.
2. Missed join to tbl_support_agents to get agent tier_level.
3. Missed GROUP BY sa.tier_level and AVG(sc.csat_score) / AVG(sc.first_response_time_minutes).

**🎯 What Was Expected (The Right Thing):**
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
*Connects agents to tickets, filters for resolved tickets with non-null CSAT, and groups by tier level.*

---

### Question 7: Top 5 Heavy Compute Consumers
**❓ Question Asked to Model:**
> *"Identify the top 5 accounts with the highest cumulative compute hours consumed across all telemetry records."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned a count of telemetry rows.
2. Missed join to tbl_accounts for client legal name.
3. Did not group by account or sum compute_hours_consumed.
4. Missed ORDER BY ... DESC LIMIT 5.

**🎯 What Was Expected (The Right Thing):**
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
*Aggregates time-series compute metrics across days for each account and ranks top 5.*

---

### Question 8: Subscription Churn Reason Analysis
**❓ Question Asked to Model:**
> *"Break down lost monthly recurring revenue and total churned contract count by cancellation reason."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Counted all subscription contracts without grouping.
2. Missed GROUP BY cancellation_reason_code.
3. Missed filtering for cancelled contracts (cancellation_date IS NOT NULL).
4. Missed converting mrr_cents to USD dollars (/ 100.0).

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT cancellation_reason_code,
       COUNT(*) AS churned_contracts_count,
       ROUND(SUM(mrr_cents) / 100.0, 2) AS lost_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NOT NULL
GROUP BY cancellation_reason_code
ORDER BY lost_mrr_usd DESC;
```
*Filters only cancelled records, groups by reason code, and calculates total lost MRR in dollars.*

---

### Question 9: Top Discounted Product Purchases
**❓ Question Asked to Model:**
> *"Show the top 3 order line items with the highest discount percentage, including product name and total line price."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_order_items;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned row count of order items.
2. Missed 3-table join: tbl_order_items -> tbl_products_catalog -> tbl_transactions_ledger.
3. Missed ORDER BY discount_pct DESC LIMIT 3.

**🎯 What Was Expected (The Right Thing):**
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
*Brings product name and transaction date alongside line-item discount details.*

---

### Question 10: Sales Rep Quota Attainment
**❓ Question Asked to Model:**
> *"Which sales representatives have achieved or exceeded their assigned quota based on settled transactions?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_sales_reps LIMIT 20;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Dumped the sales reps table without transaction data.
2. Missed 3-table join: reps -> assignments -> transactions.
3. Missed HAVING total_net_settled_usd >= quota_amount_usd.

**🎯 What Was Expected (The Right Thing):**
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
*Sums net settled cash for each rep's primary accounts and filters by attainment ratio using HAVING.*

---

### Question 11: Anomaly Detection: High 5xx Server Errors
**❓ Question Asked to Model:**
> *"Find all accounts that have experienced more 5xx server errors than 4xx client errors in telemetry."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned count of rows.
2. Missed join to tbl_accounts for company name.
3. Missed HAVING SUM(error_count_5xx) > SUM(error_count_4xx).

**🎯 What Was Expected (The Right Thing):**
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
*Compares aggregated server error count against client error count per account.*

---

### Question 12: Account Growth Cohort by Month
**❓ Question Asked to Model:**
> *"Show the number of new client accounts created per month in chronological order."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_accounts;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned all accounts without date aggregation.
2. Missed SQLite date formatting function strftime('%Y-%m', created_at).
3. Missed GROUP BY signup_month ORDER BY signup_month ASC.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT strftime('%Y-%m', created_at) AS signup_month,
       COUNT(*) AS new_accounts_count
FROM tbl_accounts
GROUP BY signup_month
ORDER BY signup_month ASC;
```
*Groups account timestamps by Year-Month to generate a monthly customer growth curve.*

---

### Question 13: Payment Gateway Settlement Stats
**❓ Question Asked to Model:**
> *"Calculate the average, minimum, and maximum net transaction amount for settled charges grouped by payment gateway."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_transactions_ledger;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Selected raw rows from transactions.
2. Missed GROUP BY gateway_provider.
3. Missed calculating AVG, MIN, and MAX on net_amt_usd with filters on SETTLED and CHARGE.

**🎯 What Was Expected (The Right Thing):**
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
*Evaluates payment gateway performance by calculating statistical spreads on settled charges.*

---

### Question 14: Multi-Contract Accounts
**❓ Question Asked to Model:**
> *"Which accounts have signed more than one subscription contract in their company history?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned count of subscription rows.
2. Missed join to tbl_accounts for company name and tier.
3. Missed GROUP BY a.acct_id HAVING COUNT(sub_contract_id) > 1.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.client_legal_name, a.tier_segment,
       COUNT(s.sub_contract_id) AS total_contracts_count
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
GROUP BY a.acct_id
HAVING COUNT(s.sub_contract_id) > 1
ORDER BY total_contracts_count DESC;
```
*Identifies recurring or expanding clients with multiple historical contracts.*

---

### Question 15: Best-Selling Add-on Product
**❓ Question Asked to Model:**
> *"What is the single best-selling add-on product by total units sold and how much gross sales did it generate?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_products_catalog;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Hit products catalog instead of joining order items for units sold.
2. Missed category filter ('STORAGE_ADDON', 'COMPUTE_BURST').
3. Missed SUM(oi.quantity) and ORDER BY total_units_sold DESC LIMIT 1.

**🎯 What Was Expected (The Right Thing):**
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
*Joins products with order items, filters add-on categories, and aggregates units sold.*

---

### Question 16: Support SLA Breach Rate by Severity
**❓ Question Asked to Model:**
> *"Group cases where first response time was greater than 60 minutes by severity level, showing count and average response time."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_support_cases LIMIT 20;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Selected arbitrary 20 cases.
2. Missed WHERE first_response_time_minutes > 60.
3. Missed GROUP BY severity_level and AVG(first_response_time_minutes).

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT severity_level,
       COUNT(*) AS delayed_cases_count,
       ROUND(AVG(first_response_time_minutes), 1) AS avg_response_mins
FROM tbl_support_cases
WHERE first_response_time_minutes > 60
GROUP BY severity_level
ORDER BY delayed_cases_count DESC;
```
*Groups ticket SLA breaches by severity to measure impact on customer response.*

---

### Question 17: Cumulative Gross Transaction Volume
**❓ Question Asked to Model:**
> *"Calculate the cumulative running total of gross transaction volume over time for settled payments."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_transactions_ledger;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Returned raw transaction rows.
2. Missed window function SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS UNBOUNDED PRECEDING).

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT tx_id, tx_timestamp, gross_amt_usd,
       ROUND(SUM(gross_amt_usd) OVER (ORDER BY tx_timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2) AS cumulative_volume_usd
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED'
LIMIT 10;
```
*Uses an analytical window function to track cumulative cash growth over chronological transactions.*

---

### Question 18: Financial Risk: Delinquent Accounts and Chargebacks
**❓ Question Asked to Model:**
> *"List all delinquent accounts or accounts with chargeback transactions, displaying total disputed amount."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_accounts;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Selected all accounts without transaction data.
2. Missed join to tbl_transactions_ledger.
3. Missed compound OR condition: acct_status_flg = 'D' OR tx_type = 'CHARGEBACK'.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.client_legal_name, a.contact_email, a.acct_status_flg,
       ROUND(SUM(ABS(t.gross_amt_usd)), 2) AS total_disputed_usd
FROM tbl_accounts a
JOIN tbl_transactions_ledger t ON a.acct_id = t.acct_id
WHERE a.acct_status_flg = 'D' OR t.tx_type = 'CHARGEBACK'
GROUP BY a.acct_id
ORDER BY total_disputed_usd DESC;
```
*Combines account status flags with transaction ledger dispute types to quantify financial exposure.*

---

### Question 19: Average Storage Consumption per Tier
**❓ Question Asked to Model:**
> *"What is the average and peak daily storage in gigabytes used by accounts across each tier segment?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_usage_telemetry;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Dumped telemetry table in isolation.
2. Missed join to tbl_accounts to get tier_segment.
3. Missed GROUP BY a.tier_segment and AVG(storage_gb_used) / MAX(storage_gb_used).

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.tier_segment,
       ROUND(AVG(u.storage_gb_used), 2) AS avg_storage_gb,
       ROUND(MAX(u.storage_gb_used), 2) AS max_storage_gb
FROM tbl_accounts a
JOIN tbl_usage_telemetry u ON a.acct_id = u.acct_id
GROUP BY a.tier_segment
ORDER BY avg_storage_gb DESC;
```
*Connects account tiers to daily infrastructure telemetry to benchmark storage usage.*

---

### Question 20: Overall Net Profit Margin
**❓ Question Asked to Model:**
> *"Calculate our overall net profit margin percentage across all settled transactions after accounting for gateway fees."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_transactions_ledger;
```

**❌ What is the Fault (The Bug / Missing Logic):**
1. Selected raw table rows.
2. Missed calculating mathematical ratio: (SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0 for settled charges.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT ROUND(SUM(gross_amt_usd), 2) AS total_gross_usd,
       ROUND(SUM(fee_deducted_usd), 2) AS total_fees_usd,
       ROUND(SUM(net_amt_usd), 2) AS total_net_usd,
       ROUND((SUM(net_amt_usd) / SUM(gross_amt_usd)) * 100.0, 2) AS net_margin_pct
FROM tbl_transactions_ledger
WHERE settlement_status = 'SETTLED' AND gross_amt_usd > 0;
```
*Computes high-level financial health by dividing net settled cash by gross payment volume.*

---

# Part B: 10 Messy / Non-Tech Stakeholder Queries

### Question 21: Big Whales Who Cancelled
**❓ Question Asked to Model (Conversational Slang):**
> *"Who are our biggest whales that cancelled on us and what excuse did they give?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_usage_telemetry LIMIT 20;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Semantic Failure: Did not understand non-tech slang 'whales' (failed to filter for VIP/Enterprise accounts).
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.client_legal_name, s.plan_code, ROUND(s.mrr_cents / 100.0, 2) AS lost_mrr_usd,
       s.cancellation_date, s.cancellation_reason_code
FROM tbl_accounts a
JOIN tbl_subscriptions_hist s ON a.acct_id = s.acct_id
WHERE s.cancellation_date IS NOT NULL AND a.tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT')
ORDER BY s.mrr_cents DESC;
```
*Translates non-tech slang 'biggest whales' to VIP/Enterprise tiers, maps 'cancelled' to non-null cancellation_date, and selects reason codes ordered by lost revenue.*

---

### Question 22: Top Cash Producer Sales Rep
**❓ Question Asked to Model (Conversational Slang):**
> *"Which sales rep is crushing it the most this year in terms of actual settled cash, not just contracts?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_subscriptions_hist ORDER BY 1 DESC LIMIT 5;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Semantic Failure: Did not translate business slang 'crushing it in settled cash' into SUM(net_amt_usd) with SETTLED filter.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Decodes 'crushing it in settled cash' to maximum sum of net_amt_usd with settlement_status = 'SETTLED' grouped by rep.*

---

### Question 23: Bleeding Accounts (Refunds > Charges)
**❓ Question Asked to Model (Conversational Slang):**
> *"Show me accounts that are bleeding us money with more refunds than actual charges."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_subscriptions_hist;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Semantic Failure: Did not translate 'bleeding us money' into HAVING refund_count > charge_count.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Translates 'bleeding us money' into conditional aggregation comparing count of refunds vs charges per account with HAVING.*

---

### Question 24: VIP Clients with Terrible Support Reviews
**❓ Question Asked to Model (Conversational Slang):**
> *"Find the VIP clients who had terrible support experience lately with really bad review scores."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_support_cases LIMIT 20;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Semantic Failure: Missed mapping 'bad review scores' to csat_score <= 2.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT a.client_legal_name, sc.case_number, sc.csat_score, sc.severity_level, sc.created_ts
FROM tbl_accounts a
JOIN tbl_support_cases sc ON a.acct_id = sc.acct_id
WHERE a.tier_segment = 'TIER_1_VIP' AND sc.csat_score <= 2
ORDER BY sc.csat_score ASC, sc.created_ts DESC;
```
*Maps 'VIP clients' to tier_segment = 'TIER_1_VIP' and 'bad review scores' to csat_score <= 2, joining accounts with support cases.*

---

### Question 25: Total MRR in Plain Dollars
**❓ Question Asked to Model (Conversational Slang):**
> *"What's our total monthly recurring revenue right now in plain dollars, not pennies?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_subscriptions_hist;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Math & Unit Failure: Ignored user's explicit request for 'plain dollars, not pennies' (failed to divide mrr_cents by 100.0).

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT ROUND(SUM(mrr_cents) / 100.0, 2) AS total_active_mrr_usd
FROM tbl_subscriptions_hist
WHERE cancellation_date IS NULL;
```
*Understands 'plain dollars, not pennies' requires dividing mrr_cents by 100.0 for active subscriptions.*

---

### Question 26: Silent Sufferers (Errors with No Ticket)
**❓ Question Asked to Model (Conversational Slang):**
> *"Are there any accounts getting hammered with server errors but nobody filed a ticket for them?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_transactions_ledger;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Relational Logic Failure: Failed to apply LEFT JOIN with NULL check to identify silent sufferers without support cases.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Understands 'nobody filed a ticket' implies a LEFT JOIN on tbl_support_cases with WHERE sc.case_number IS NULL and positive 5xx errors.*

---

### Question 27: Add-ons Bundled with Enterprise Plans
**❓ Question Asked to Model (Conversational Slang):**
> *"Which products are driving the most money when bundled with our big enterprise plans?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_subscriptions_hist ORDER BY 1 DESC LIMIT 5;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Links products, order items, transactions, and subscriptions with plan_code = 'PLAN_ENT_CUSTOM'.*

---

### Question 28: Delinquent European Clients
**❓ Question Asked to Model (Conversational Slang):**
> *"Give me a list of folks in Europe who haven't paid their bills and are suspended."*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_accounts LIMIT 20;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
Basic single-table query generated without full relational complexity.

**🎯 What Was Expected (The Right Thing):**
```sql
SELECT client_legal_name, contact_person, contact_email, country_iso3, acct_status_flg
FROM tbl_accounts
WHERE country_iso3 IN ('DEU', 'GBR', 'FRA') AND acct_status_flg IN ('S', 'D');
```
*Translates 'Europe' to European ISO codes (DEU, GBR, FRA) and 'haven't paid and suspended' to status flags 'S' and 'D'.*

---

### Question 29: Slowest Agent on Critical Outages
**❓ Question Asked to Model (Conversational Slang):**
> *"Who is our slowest support agent to reply when a customer has a critical emergency blocker?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT * FROM tbl_support_cases LIMIT 20;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Ranking Failure: Failed to calculate average response time and sort descending to find the slowest agent.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Translates 'critical emergency blocker' to SEV_1_BLOCKER and 'slowest support agent' to MAX(AVG(first_response_time_minutes)).*

---

### Question 30: Cheap Tier Heavy Compute Hogs
**❓ Question Asked to Model (Conversational Slang):**
> *"Which accounts used an insane amount of compute hours last week but are only on our cheap starter tier?"*

**🤖 What the Agent Actually Generated:**
```sql
SELECT COUNT(*) AS total_count FROM tbl_usage_telemetry;
```

**❌ What is the Fault (The Bug / Semantic Misunderstanding):**
1. Tier Mapping Failure: Failed to map 'cheap starter tier' to TIER_4_SMB.
2. Missing Multi-Table JOIN: The query required joining multiple tables, but only queried a single table.

**🎯 What Was Expected (The Right Thing):**
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
*Translates 'cheap starter tier' to TIER_4_SMB and 'insane amount of compute hours' to ORDER BY SUM(compute_hours_consumed) DESC.*

---
