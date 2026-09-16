import sqlite3
import os
from datetime import datetime, timedelta
import random

def build_enterprise_database(db_path: str = "company.sqlite"):
    """
    Creates a realistic enterprise SQLite database with multi-table relationships,
    realistic naming conventions (cryptic prefixes, status flags), and sample data.
    """
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Customers Table (with legacy/enterprise column naming)
    cursor.execute("""
    CREATE TABLE tbl_customers (
        cust_id INTEGER PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        country_code TEXT NOT NULL,
        tier TEXT CHECK(tier IN ('FREE', 'STARTER', 'GROWTH', 'ENTERPRISE')),
        created_at TEXT NOT NULL
    );
    """)

    # 2. Subscriptions Table
    cursor.execute("""
    CREATE TABLE tbl_subscriptions (
        sub_id INTEGER PRIMARY KEY,
        cust_id INTEGER NOT NULL,
        plan_name TEXT NOT NULL,
        monthly_mrr_usd REAL NOT NULL,
        is_cancelled INTEGER DEFAULT 0,
        cancel_reason TEXT,
        started_at TEXT NOT NULL,
        FOREIGN KEY (cust_id) REFERENCES tbl_customers(cust_id)
    );
    """)

    # 3. Orders / Transactions Table
    cursor.execute("""
    CREATE TABLE tbl_orders (
        order_id INTEGER PRIMARY KEY,
        cust_id INTEGER NOT NULL,
        order_timestamp TEXT NOT NULL,
        order_amount_usd REAL NOT NULL,
        fulfillment_status TEXT CHECK(fulfillment_status IN ('PENDING', 'SHIPPED', 'DELIVERED', 'REFUNDED')),
        payment_method TEXT,
        FOREIGN KEY (cust_id) REFERENCES tbl_customers(cust_id)
    );
    """)

    # 4. Customer Support Tickets Table
    cursor.execute("""
    CREATE TABLE tbl_support_tickets (
        ticket_id INTEGER PRIMARY KEY,
        cust_id INTEGER NOT NULL,
        priority_lvl TEXT CHECK(priority_lvl IN ('P1_CRITICAL', 'P2_HIGH', 'P3_NORMAL')),
        resolved_flag INTEGER DEFAULT 0,
        issue_category TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (cust_id) REFERENCES tbl_customers(cust_id)
    );
    """)

    # --- Seed Realistic Data ---
    customers_data = [
        (101, "Alice Morgan", "alice.m@acmecorp.com", "US", "ENTERPRISE", "2023-01-15 08:30:00"),
        (102, "Bob Zhang", "bzhang@techwave.io", "US", "GROWTH", "2023-03-22 14:15:00"),
        (103, "Carla Rossi", "carla@rossi-design.de", "DE", "STARTER", "2023-06-10 11:00:00"),
        (104, "David Kumar", "david.k@finpeak.in", "IN", "ENTERPRISE", "2023-08-01 09:45:00"),
        (105, "Elena Petrova", "elena@nordicscale.se", "SE", "FREE", "2023-11-20 16:20:00"),
        (106, "Farhan Al-Mansoor", "farhan@gulfstream.ae", "AE", "ENTERPRISE", "2024-01-05 10:10:00"),
        (107, "Grace Hopper", "grace@compilertech.org", "US", "GROWTH", "2024-02-14 13:00:00"),
        (108, "Hiroshi Tanaka", "hiroshi@tokyolab.jp", "JP", "STARTER", "2024-03-01 07:30:00"),
        (109, "Isabella Santos", "isabella@rioventures.br", "BR", "FREE", "2024-04-18 17:50:00"),
        (110, "Jack Wilson", "jack@wilsonlogistics.co.uk", "GB", "ENTERPRISE", "2024-05-30 12:00:00")
    ]
    cursor.executemany("INSERT INTO tbl_customers VALUES (?, ?, ?, ?, ?, ?)", customers_data)

    subscriptions_data = [
        (1001, 101, "Enterprise_Dedicated", 2499.00, 0, None, "2023-01-15"),
        (1002, 102, "Growth_Standard", 499.00, 0, None, "2023-03-22"),
        (1003, 103, "Starter_Monthly", 99.00, 1, "High Price", "2023-06-10"),
        (1004, 104, "Enterprise_Dedicated", 3999.00, 0, None, "2023-08-01"),
        (1005, 105, "Free_Tier", 0.00, 0, None, "2023-11-20"),
        (1006, 106, "Enterprise_Dedicated", 1999.00, 1, "Migration to competitor", "2024-01-05"),
        (1007, 107, "Growth_Standard", 499.00, 0, None, "2024-02-14"),
        (1008, 108, "Starter_Monthly", 99.00, 0, None, "2024-03-01"),
        (1009, 109, "Free_Tier", 0.00, 0, None, "2024-04-18"),
        (1010, 110, "Enterprise_Custom", 4500.00, 0, None, "2024-05-30")
    ]
    cursor.executemany("INSERT INTO tbl_subscriptions VALUES (?, ?, ?, ?, ?, ?, ?)", subscriptions_data)

    orders_data = [
        (5001, 101, "2024-02-01 10:00:00", 12500.00, "DELIVERED", "WIRE_TRANSFER"),
        (5002, 101, "2024-04-15 11:30:00", 8200.00, "DELIVERED", "WIRE_TRANSFER"),
        (5003, 102, "2024-03-01 14:20:00", 1499.00, "DELIVERED", "CREDIT_CARD"),
        (5004, 103, "2024-01-10 09:15:00", 299.00, "REFUNDED", "PAYPAL"),
        (5005, 104, "2024-05-02 16:45:00", 24000.00, "DELIVERED", "WIRE_TRANSFER"),
        (5006, 106, "2024-02-20 18:00:00", 5000.00, "DELIVERED", "CREDIT_CARD"),
        (5007, 107, "2024-06-12 12:00:00", 999.00, "PENDING", "CREDIT_CARD"),
        (5008, 110, "2024-06-01 15:30:00", 18500.00, "DELIVERED", "WIRE_TRANSFER")
    ]
    cursor.executemany("INSERT INTO tbl_orders VALUES (?, ?, ?, ?, ?, ?)", orders_data)

    tickets_data = [
        (9001, 106, "P1_CRITICAL", 0, "Downtime during batch job", "2024-06-14 08:00:00"),
        (9002, 101, "P3_NORMAL", 1, "Invoice address update", "2024-03-10 11:00:00"),
        (9003, 104, "P2_HIGH", 0, "Latency on API gateway", "2024-06-15 14:30:00"),
        (9004, 103, "P1_CRITICAL", 1, "Billing dispute on cancelled plan", "2024-02-12 16:00:00"),
        (9005, 102, "P3_NORMAL", 1, "Feature request for CSV export", "2024-04-05 09:20:00")
    ]
    cursor.executemany("INSERT INTO tbl_support_tickets VALUES (?, ?, ?, ?, ?, ?)", tickets_data)

    conn.commit()
    conn.close()
    print(f"✔ Successfully generated realistic enterprise database at: {os.path.abspath(db_path)}")

if __name__ == "__main__":
    build_enterprise_database()
