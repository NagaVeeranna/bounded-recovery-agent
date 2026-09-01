import sqlite3
import json
from datetime import datetime, timezone
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fintech_agent.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop existing tables to ensure fresh schema
    cursor.execute("DROP TABLE IF EXISTS audit_log")
    cursor.execute("DROP TABLE IF EXISTS customers")

    # Customers table with behavioral metrics, LTV, and idempotency status
    cursor.execute("""
    CREATE TABLE customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        mrr REAL NOT NULL,
        days_since_active INTEGER NOT NULL,
        failed_payment_count INTEGER NOT NULL,
        support_tickets_30d INTEGER NOT NULL,
        usage_drop_pct REAL NOT NULL,
        card_expiring_soon INTEGER NOT NULL, -- 1 if expiring in < 7 days, 0 otherwise
        has_discount INTEGER DEFAULT 0, -- 1 if active discount exists
        risk_score REAL DEFAULT 0.0, -- ML Risk Score (0-100%)
        risk_status TEXT DEFAULT 'UNEVALUATED', -- 'HEALTHY', 'AT_RISK'
        processed INTEGER DEFAULT 0, -- Idempotency flag: 1 if already acted upon
        processed_at TEXT,
        status TEXT DEFAULT 'ACTIVE' -- 'ACTIVE', 'RETAINED', 'CHURNED', 'PAUSED'
    )
    """)

    # Audit_Log table: Append-only ledger of all predictive, reasoning, and interceptor decisions
    cursor.execute("""
    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        ml_risk_score REAL NOT NULL,
        raw_llm_reasoning TEXT,
        proposed_action TEXT,
        action_params TEXT,
        guardrail_status TEXT NOT NULL, -- 'APPROVED', 'BLOCKED', 'AUTO_REMEDIATED'
        policy_violation_reason TEXT,
        final_executed_action TEXT,
        execution_details TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    )
    """)

    conn.commit()
    conn.close()

def seed_synthetic_data():
    """
    Populates database with realistic synthetic data covering 3 distinct customer personas:
    1. Healthy Users (Low risk)
    2. Card Expiration Users (High risk due to payment failure, active product usage)
    3. Ghosting Users (High risk due to zero activity & heavy usage drop)
    """
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    synthetic_customers = [
        # --- Persona 1: Healthy Users (Low churn risk) ---
        {
            "id": "CUST-101",
            "name": "Sarah Jenkins",
            "email": "sarah.j@apexlogistics.io",
            "plan_type": "Enterprise Pro",
            "mrr": 499.00,
            "days_since_active": 1,
            "failed_payment_count": 0,
            "support_tickets_30d": 0,
            "usage_drop_pct": 2.5,
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-102",
            "name": "David Chen",
            "email": "dchen@nexuscloud.com",
            "plan_type": "Growth Tier",
            "mrr": 199.00,
            "days_since_active": 2,
            "failed_payment_count": 0,
            "support_tickets_30d": 1,
            "usage_drop_pct": 5.0,
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        # --- Persona 2: Card Expiration Users (At-risk payment failure) ---
        {
            "id": "CUST-201",
            "name": "Elena Rostova",
            "email": "elena@fintechglobal.org",
            "plan_type": "Enterprise Pro",
            "mrr": 799.00,
            "days_since_active": 1,
            "failed_payment_count": 2,
            "support_tickets_30d": 2,
            "usage_drop_pct": 8.0,
            "card_expiring_soon": 1,
            "has_discount": 0
        },
        {
            "id": "CUST-202",
            "name": "Marcus Vance",
            "email": "marcus@vancemedia.co",
            "plan_type": "Growth Tier",
            "mrr": 299.00,
            "days_since_active": 3,
            "failed_payment_count": 1,
            "support_tickets_30d": 0,
            "usage_drop_pct": 12.0,
            "card_expiring_soon": 1,
            "has_discount": 0
        },
        # --- Persona 3: Ghosting Users (Severe usage drop & high inactive days) ---
        {
            "id": "CUST-301",
            "name": "TechCorp Solutions (Robert Sterling)",
            "email": "rsterling@techcorpsolutions.com",
            "plan_type": "Enterprise Tier",
            "mrr": 1200.00,
            "days_since_active": 28,
            "failed_payment_count": 0,
            "support_tickets_30d": 5,
            "usage_drop_pct": 88.5,
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-302",
            "name": "Amanda Vance",
            "email": "amanda@brightdesign.agency",
            "plan_type": "Starter Tier",
            "mrr": 99.00,
            "days_since_active": 35,
            "failed_payment_count": 1,
            "support_tickets_30d": 3,
            "usage_drop_pct": 92.0,
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        # --- Edge Case: At-risk User with existing discount (Testing Double-Discount Guard) ---
        {
            "id": "CUST-303",
            "name": "HyperScale Ventures (Leo Miller)",
            "email": "leo@hyperscale.io",
            "plan_type": "Scale Tier",
            "mrr": 650.00,
            "days_since_active": 22,
            "failed_payment_count": 1,
            "support_tickets_30d": 4,
            "usage_drop_pct": 79.0,
            "card_expiring_soon": 0,
            "has_discount": 1 # ALREADY HAS A DISCOUNT!
        }
    ]

    for c in synthetic_customers:
        cursor.execute("""
        INSERT INTO customers (id, name, email, plan_type, mrr, days_since_active, 
                              failed_payment_count, support_tickets_30d, usage_drop_pct, 
                              card_expiring_soon, has_discount)
        VALUES (:id, :name, :email, :plan_type, :mrr, :days_since_active, 
                :failed_payment_count, :support_tickets_30d, :usage_drop_pct, 
                :card_expiring_soon, :has_discount)
        """, c)

    conn.commit()
    conn.close()
    print(f"Successfully initialized database with {len(synthetic_customers)} synthetic customers.")

def update_customer_risk(customer_id, risk_score, risk_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE customers 
    SET risk_score = ?, risk_status = ? 
    WHERE id = ?
    """, (risk_score, risk_status, customer_id))
    conn.commit()
    conn.close()

def mark_customer_processed(customer_id, new_status="RETAINED"):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    UPDATE customers 
    SET processed = 1, processed_at = ?, status = ? 
    WHERE id = ?
    """, (now_iso, new_status, customer_id))
    conn.commit()
    conn.close()

def log_audit_entry(customer_id, ml_risk_score, raw_llm_reasoning, proposed_action, 
                    action_params, guardrail_status, policy_violation_reason, 
                    final_executed_action, execution_details):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    params_json = json.dumps(action_params) if isinstance(action_params, dict) else str(action_params)
    details_json = json.dumps(execution_details) if isinstance(execution_details, dict) else str(execution_details)

    cursor.execute("""
    INSERT INTO audit_log (customer_id, timestamp, ml_risk_score, raw_llm_reasoning,
                           proposed_action, action_params, guardrail_status, 
                           policy_violation_reason, final_executed_action, execution_details)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (customer_id, now_iso, ml_risk_score, raw_llm_reasoning, proposed_action,
          params_json, guardrail_status, policy_violation_reason, final_executed_action, details_json))
    
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id

def get_all_customers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_customer_by_id(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_audit_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.*, c.name as customer_name, c.email as customer_email, c.mrr, c.plan_type
    FROM audit_log a
    JOIN customers c ON a.customer_id = c.id
    ORDER BY a.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    seed_synthetic_data()
