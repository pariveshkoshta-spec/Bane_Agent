import sqlite3
import os
import random
from datetime import datetime, timedelta

def build_complex_enterprise_db(db_path: str = "enterprise_nexus.sqlite"):
    """
    Generates a massive, interconnected, realistic enterprise SQLite database.
    10 tables, cryptic naming, cross-table foreign keys, mixed units, and hundreds of rows.
    """
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Accounts (Company Profiles)
    cursor.execute("""
    CREATE TABLE tbl_accounts (
        acct_id INTEGER PRIMARY KEY,
        org_code TEXT NOT NULL,
        client_legal_name TEXT NOT NULL,
        contact_person TEXT NOT NULL,
        contact_email TEXT UNIQUE NOT NULL,
        tier_segment TEXT CHECK(tier_segment IN ('TIER_1_VIP', 'TIER_2_ENT', 'TIER_3_MID', 'TIER_4_SMB', 'INTERNAL')),
        acct_status_flg TEXT CHECK(acct_status_flg IN ('A', 'I', 'S', 'D')), -- A=Active, I=Inactive, S=Suspended, D=Delinquent
        created_at TEXT NOT NULL,
        country_iso3 TEXT NOT NULL
    );
    """)

    # 2. Sales Representatives
    cursor.execute("""
    CREATE TABLE tbl_sales_reps (
        rep_id INTEGER PRIMARY KEY,
        rep_name TEXT NOT NULL,
        quota_amount_usd REAL NOT NULL,
        territory TEXT NOT NULL
    );
    """)

    # 3. Account to Sales Rep Assignment
    cursor.execute("""
    CREATE TABLE tbl_account_assignments (
        assignment_id INTEGER PRIMARY KEY,
        acct_id INTEGER NOT NULL,
        rep_id INTEGER NOT NULL,
        assigned_since TEXT NOT NULL,
        is_primary_owner INTEGER DEFAULT 1,
        FOREIGN KEY (acct_id) REFERENCES tbl_accounts(acct_id),
        FOREIGN KEY (rep_id) REFERENCES tbl_sales_reps(rep_id)
    );
    """)

    # 4. Subscription Contracts History
    cursor.execute("""
    CREATE TABLE tbl_subscriptions_hist (
        sub_contract_id INTEGER PRIMARY KEY,
        acct_id INTEGER NOT NULL,
        plan_code TEXT NOT NULL,
        mrr_cents INTEGER NOT NULL, -- Stored in CENTS (e.g. 250000 = $2,500.00)
        billing_cycle TEXT CHECK(billing_cycle IN ('MONTHLY', 'ANNUAL', 'QUARTERLY')),
        auto_renew_flag INTEGER DEFAULT 1,
        start_date TEXT NOT NULL,
        cancellation_date TEXT,
        cancellation_reason_code TEXT,
        FOREIGN KEY (acct_id) REFERENCES tbl_accounts(acct_id)
    );
    """)

    # 5. Products Catalog
    cursor.execute("""
    CREATE TABLE tbl_products_catalog (
        prod_sku TEXT PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit_price_usd REAL NOT NULL,
        is_deprecated INTEGER DEFAULT 0
    );
    """)

    # 6. Transactions & Payment Ledger
    cursor.execute("""
    CREATE TABLE tbl_transactions_ledger (
        tx_id INTEGER PRIMARY KEY,
        acct_id INTEGER NOT NULL,
        sub_contract_id INTEGER,
        tx_timestamp TEXT NOT NULL,
        gross_amt_usd REAL NOT NULL,
        fee_deducted_usd REAL NOT NULL,
        net_amt_usd REAL NOT NULL,
        tx_type TEXT CHECK(tx_type IN ('CHARGE', 'REFUND', 'CHARGEBACK', 'CREDIT_ADJUSTMENT')),
        settlement_status TEXT CHECK(settlement_status IN ('SETTLED', 'PENDING', 'FAILED', 'REVERSED')),
        gateway_provider TEXT NOT NULL,
        FOREIGN KEY (acct_id) REFERENCES tbl_accounts(acct_id),
        FOREIGN KEY (sub_contract_id) REFERENCES tbl_subscriptions_hist(sub_contract_id)
    );
    """)

    # 7. Order Line Items Breakdown
    cursor.execute("""
    CREATE TABLE tbl_order_items (
        line_item_id INTEGER PRIMARY KEY,
        tx_id INTEGER NOT NULL,
        prod_sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        discount_pct REAL DEFAULT 0.0,
        line_total_usd REAL NOT NULL,
        FOREIGN KEY (tx_id) REFERENCES tbl_transactions_ledger(tx_id),
        FOREIGN KEY (prod_sku) REFERENCES tbl_products_catalog(prod_sku)
    );
    """)

    # 8. Support Agents
    cursor.execute("""
    CREATE TABLE tbl_support_agents (
        agent_id INTEGER PRIMARY KEY,
        agent_full_name TEXT NOT NULL,
        region TEXT NOT NULL,
        tier_level INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    """)

    # 9. Support Cases
    cursor.execute("""
    CREATE TABLE tbl_support_cases (
        case_number INTEGER PRIMARY KEY,
        acct_id INTEGER NOT NULL,
        assigned_agent_id INTEGER,
        severity_level TEXT CHECK(severity_level IN ('SEV_1_BLOCKER', 'SEV_2_DEGRADED', 'SEV_3_MINOR', 'SEV_4_INFO')),
        case_status TEXT CHECK(case_status IN ('OPEN', 'INVESTIGATING', 'PENDING_CUSTOMER', 'RESOLVED', 'CLOSED_NO_FIX')),
        first_response_time_minutes INTEGER,
        csat_score INTEGER CHECK(csat_score BETWEEN 1 AND 5),
        created_ts TEXT NOT NULL,
        resolved_ts TEXT,
        FOREIGN KEY (acct_id) REFERENCES tbl_accounts(acct_id),
        FOREIGN KEY (assigned_agent_id) REFERENCES tbl_support_agents(agent_id)
    );
    """)

    # 10. Daily Usage Telemetry
    cursor.execute("""
    CREATE TABLE tbl_usage_telemetry (
        telemetry_id INTEGER PRIMARY KEY,
        acct_id INTEGER NOT NULL,
        activity_date TEXT NOT NULL,
        api_calls_count INTEGER NOT NULL,
        compute_hours_consumed REAL NOT NULL,
        storage_gb_used REAL NOT NULL,
        error_count_4xx INTEGER DEFAULT 0,
        error_count_5xx INTEGER DEFAULT 0,
        FOREIGN KEY (acct_id) REFERENCES tbl_accounts(acct_id)
    );
    """)

    print("[1/5] Database DDL schema created with 10 tables.")

    # --- POPULATE REALISTIC DATA ---
    random.seed(42)

    # 1. Populate Sales Reps (10 reps)
    reps = [
        (201, "Marcus Vance", 1200000.0, "EAST_US"),
        (202, "Sarah Jenkins", 1500000.0, "WEST_US"),
        (203, "Klaus Schneider", 1100000.0, "DACH"),
        (204, "Emily Watson", 1350000.0, "UK_IRELAND"),
        (205, "Kenji Sato", 900000.0, "JAPAC"),
        (206, "Sofia Ramirez", 850000.0, "LATAM"),
        (207, "Liam O'Connor", 1000000.0, "EMEA_NORTH"),
        (208, "Priya Sharma", 1150000.0, "INDIA_SOUTHASIA"),
        (209, "Chen Wei", 1400000.0, "APAC_GREATER_CHINA"),
        (210, "Chloe Dubois", 950000.0, "FRANCE_BENELUX")
    ]
    cursor.executemany("INSERT INTO tbl_sales_reps VALUES (?, ?, ?, ?)", reps)

    # 2. Populate Products Catalog (8 products)
    products = [
        ("SKU-CORE-ENT", "Core Enterprise Platform License", "CORE_PLATFORM", 5000.00, 0),
        ("SKU-CORE-PRO", "Core Professional License", "CORE_PLATFORM", 1500.00, 0),
        ("SKU-CORE-STARTER", "Core Starter License", "CORE_PLATFORM", 300.00, 0),
        ("SKU-ADDON-STORAGE", "10TB High-Speed Storage Addon", "STORAGE_ADDON", 450.00, 0),
        ("SKU-COMPUTE-BURST", "GPU Dedicated Compute Burst (100h)", "COMPUTE_BURST", 1200.00, 0),
        ("SKU-AI-TOKENS-1M", "10M Tokens LLM Gateway Quota", "COMPUTE_BURST", 250.00, 0),
        ("SKU-SUPPORT-PREMIUM", "24/7 Dedicated Support SLA Addon", "CONSULTING_SVC", 2000.00, 0),
        ("SKU-LEGACY-V1", "Legacy Sync Connector (Deprecated)", "CORE_PLATFORM", 100.00, 1)
    ]
    cursor.executemany("INSERT INTO tbl_products_catalog VALUES (?, ?, ?, ?, ?)", products)

    # 3. Populate Support Agents (8 agents)
    agents = [
        (301, "Alex Mercer", "AMER", 3, 1),
        (302, "Brenda Lee", "AMER", 2, 1),
        (303, "Cedric Moulin", "EMEA", 3, 1),
        (304, "Daria Ivanova", "EMEA", 1, 1),
        (305, "Emi Takahashi", "APAC", 2, 1),
        (306, "Fahad Qasim", "EMEA", 2, 0), # Inactive agent
        (307, "Gabriel Santos", "AMER", 1, 1),
        (308, "Haruto Watanabe", "APAC", 3, 1)
    ]
    cursor.executemany("INSERT INTO tbl_support_agents VALUES (?, ?, ?, ?, ?)", agents)

    # 4. Populate Accounts (50 realistic accounts)
    company_names = [
        "Acme Global", "Nexus Technologies", "FinPeak Wealth", "Vertex Biotech", "OmniCloud Services",
        "Aura Retailers", "Cobalt Dynamics", "Horizon Logistics", "Zephyr AI Systems", "Titan Minerals",
        "Starlight Media", "Vanguard Aerospace", "Solaria Energy", "Epsilon Robotics", "Borealis Health",
        "CyberNetics Labs", "Krypton Labs", "Atlas Maritime", "Hyperion Analytics", "Pacific Trading Co",
        "Delta Consulting", "Echo Mobile", "Pinnacle Capital", "Meridian Telecom", "Quantum Software",
        "Beacon Security", "Frontier Media", "Summit Agro", "Oasis Hospitality", "Silverline Auto",
        "Redwood Payments", "BlueWave Marine", "Ironclad Cloud", "Aegis Insurance", "Pulse Medical",
        "Synapse Networks", "Polaris Defense", "Vortex Digital", "Helios Solar", "Apex Manufacturing",
        "Terraform RealEstate", "Galactic Gaming", "TrueNorth Foods", "Matrix Engineering", "Castor Financial",
        "Lyra Fashion", "Orion Chemicals", "Nova Pharma", "Strata Architecture", "Zenith CleanTech"
    ]

    countries = ["USA", "DEU", "GBR", "IND", "SGP", "JPN", "CAN", "FRA", "AUS", "BRA"]
    tiers = ["TIER_1_VIP", "TIER_2_ENT", "TIER_3_MID", "TIER_4_SMB"]
    statuses = ["A", "A", "A", "A", "I", "S", "D"] # mostly active, some inactive/suspended/delinquent

    accounts = []
    assignments = []
    base_date = datetime(2023, 1, 1)

    for i in range(1, 51):
        acct_id = 1000 + i
        org_code = f"ORG_{random.choice(countries)}"
        client_name = company_names[i-1]
        contact_name = f"Contact_{i} Person"
        email = f"lead_{i}@{client_name.lower().replace(' ', '').replace('.', '')}.com"
        tier = random.choice(tiers)
        status = random.choice(statuses)
        created_dt = base_date + timedelta(days=random.randint(0, 450))
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
        country = random.choice(countries)

        accounts.append((acct_id, org_code, client_name, contact_name, email, tier, status, created_str, country))

        # Assign a sales rep
        rep_id = random.choice(reps)[0]
        assignments.append((2000 + i, acct_id, rep_id, created_str[:10], 1))

    cursor.executemany("INSERT INTO tbl_accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", accounts)
    cursor.executemany("INSERT INTO tbl_account_assignments VALUES (?, ?, ?, ?, ?)", assignments)

    print("[2/5] Accounts, Reps, and Products seeded.")

    # 5. Populate Subscriptions History (75 contracts across accounts)
    plans = [
        ("PLAN_ENT_CUSTOM", 500000, "ANNUAL"),
        ("PLAN_PRO_ANNUAL", 180000, "ANNUAL"),
        ("PLAN_STARTER_MO", 35000, "MONTHLY"),
        ("PLAN_GROWTH_QUART", 120000, "QUARTERLY")
    ]
    cancel_reasons = ["PRICE_HIGH", "LACK_USAGE", "MIGRATED_COMPETITOR", "BAD_SUPPORT", "BUDGET_CUTS"]

    subscriptions = []
    sub_id_counter = 5001
    for acct in accounts:
        acct_id = acct[0]
        created_dt = datetime.strptime(acct[7], "%Y-%m-%d %H:%M:%S")
        # 1 to 2 contracts per account
        num_subs = random.choice([1, 1, 2])
        for s in range(num_subs):
            plan_code, mrr_cents, cycle = random.choice(plans)
            is_cancelled = random.choice([0, 0, 0, 1])
            start_dt = created_dt + timedelta(days=random.randint(5, 30))
            start_str = start_dt.strftime("%Y-%m-%d")
            cancel_str = None
            cancel_reason = None
            auto_renew = 1

            if is_cancelled or acct[6] in ('I', 'D'):
                is_cancelled = 1
                auto_renew = 0
                cancel_dt = start_dt + timedelta(days=random.randint(60, 200))
                cancel_str = cancel_dt.strftime("%Y-%m-%d")
                cancel_reason = random.choice(cancel_reasons)

            subscriptions.append((sub_id_counter, acct_id, plan_code, mrr_cents, cycle, auto_renew, start_str, cancel_str, cancel_reason))
            sub_id_counter += 1

    cursor.executemany("INSERT INTO tbl_subscriptions_hist VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", subscriptions)

    # 6. Populate Transactions & Order Line Items (150 transactions)
    tx_types = ["CHARGE", "CHARGE", "CHARGE", "CHARGE", "REFUND", "CHARGEBACK"]
    settlements = ["SETTLED", "SETTLED", "SETTLED", "SETTLED", "PENDING", "FAILED"]
    gateways = ["STRIPE_PROD", "WIRE_ACH", "PAYPAL_DIRECT", "ADYEN_GLOBAL"]

    transactions = []
    order_items = []
    tx_counter = 80001
    line_counter = 90001

    for sub in subscriptions:
        sub_id = sub[0]
        acct_id = sub[1]
        mrr_usd = sub[3] / 100.0 # Convert cents to USD
        num_tx = random.randint(1, 4)
        sub_start = datetime.strptime(sub[6], "%Y-%m-%d")

        for t in range(num_tx):
            tx_dt = sub_start + timedelta(days=t * 30 + random.randint(1, 5))
            tx_str = tx_dt.strftime("%Y-%m-%d %H:%M:%S")
            tx_type = random.choice(tx_types)
            settlement = random.choice(settlements)
            gateway = random.choice(gateways)
            gross_amt = mrr_usd * (1.0 if sub[4] == "MONTHLY" else 3.0 if sub[4] == "QUARTERLY" else 12.0)
            fee = round(gross_amt * 0.029 + 0.30, 2)
            net_amt = round(gross_amt - fee, 2)

            if tx_type in ("REFUND", "CHARGEBACK"):
                gross_amt = -abs(gross_amt)
                net_amt = -abs(net_amt)

            transactions.append((tx_counter, acct_id, sub_id, tx_str, gross_amt, fee, net_amt, tx_type, settlement, gateway))

            # Add 1-2 line items for each transaction
            chosen_sku = "SKU-CORE-ENT" if mrr_usd >= 4000 else "SKU-CORE-PRO" if mrr_usd >= 1000 else "SKU-CORE-STARTER"
            sku_obj = next(p for p in products if p[0] == chosen_sku)
            order_items.append((line_counter, tx_counter, chosen_sku, 1, 0.0, sku_obj[3]))
            line_counter += 1

            # Optional addon
            if random.random() > 0.6:
                addon_sku = random.choice(["SKU-ADDON-STORAGE", "SKU-COMPUTE-BURST", "SKU-AI-TOKENS-1M"])
                addon_obj = next(p for p in products if p[0] == addon_sku)
                order_items.append((line_counter, tx_counter, addon_sku, random.randint(1, 3), 0.10, addon_obj[3] * 0.90))
                line_counter += 1

            tx_counter += 1

    cursor.executemany("INSERT INTO tbl_transactions_ledger VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", transactions)
    cursor.executemany("INSERT INTO tbl_order_items VALUES (?, ?, ?, ?, ?, ?)", order_items)

    print("[3/5] Subscriptions and Transactions seeded.")

    # 7. Populate Support Cases (120 cases)
    severities = ["SEV_1_BLOCKER", "SEV_2_DEGRADED", "SEV_3_MINOR", "SEV_4_INFO"]
    case_statuses = ["RESOLVED", "RESOLVED", "RESOLVED", "OPEN", "INVESTIGATING", "CLOSED_NO_FIX"]
    cases = []
    case_counter = 70001

    for _ in range(120):
        acct_id = random.choice(accounts)[0]
        agent_id = random.choice(agents)[0]
        severity = random.choice(severities)
        c_status = random.choice(case_statuses)
        resp_time = random.randint(5, 180)
        csat = random.choice([1, 2, 3, 4, 5, 5, 5, None])
        c_date = base_date + timedelta(days=random.randint(30, 480))
        c_date_str = c_date.strftime("%Y-%m-%d %H:%M:%S")
        res_date_str = None
        if c_status in ("RESOLVED", "CLOSED_NO_FIX"):
            res_date = c_date + timedelta(hours=random.randint(1, 72))
            res_date_str = res_date.strftime("%Y-%m-%d %H:%M:%S")

        cases.append((case_counter, acct_id, agent_id, severity, c_status, resp_time, csat, c_date_str, res_date_str))
        case_counter += 1

    cursor.executemany("INSERT INTO tbl_support_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", cases)

    # 8. Populate Usage Telemetry (300 daily telemetry records)
    telemetry = []
    telem_counter = 1
    for acct in accounts[:30]: # First 30 accounts have continuous telemetry
        acct_id = acct[0]
        start_telem = datetime(2024, 5, 1)
        for d in range(10): # 10 days of data per account
            telem_dt = (start_telem + timedelta(days=d)).strftime("%Y-%m-%d")
            api_calls = random.randint(5000, 250000)
            compute_h = round(random.uniform(5.5, 95.0), 2)
            storage_gb = round(random.uniform(50.0, 1200.0), 2)
            err_4xx = random.randint(0, 150)
            err_5xx = random.randint(0, 15)
            telemetry.append((telem_counter, acct_id, telem_dt, api_calls, compute_h, storage_gb, err_4xx, err_5xx))
            telem_counter += 1

    cursor.executemany("INSERT INTO tbl_usage_telemetry VALUES (?, ?, ?, ?, ?, ?, ?, ?)", telemetry)

    conn.commit()
    conn.close()
    print(f"[4/5] Telemetry and Cases seeded.")
    print(f"[5/5] ✔ Successfully generated enterprise database at: {os.path.abspath(db_path)}")

if __name__ == "__main__":
    build_complex_enterprise_db()
