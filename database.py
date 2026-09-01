import sqlite3
import json
from datetime import datetime, timezone
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fintech_agent.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_recreate=False):
    conn = get_db_connection()
    cursor = conn.cursor()

    if force_recreate:
        cursor.execute("DROP TABLE IF EXISTS audit_log")
        cursor.execute("DROP TABLE IF EXISTS webhooks_log")
        cursor.execute("DROP TABLE IF EXISTS customers")

    # Customers table with merchant & payment behavior metrics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        merchant_category TEXT NOT NULL,
        mrr REAL NOT NULL,
        avg_transaction_value REAL NOT NULL,
        days_since_last_transaction INTEGER NOT NULL,
        payment_failure_rate REAL NOT NULL,
        failed_payment_count INTEGER NOT NULL,
        mandate_status TEXT DEFAULT 'ACTIVE',
        card_expiring_soon INTEGER NOT NULL,
        has_discount INTEGER DEFAULT 0,
        risk_score REAL DEFAULT 0.0,
        risk_status TEXT DEFAULT 'UNEVALUATED',
        processed INTEGER DEFAULT 0,
        processed_at TEXT,
        status TEXT DEFAULT 'ACTIVE'
    )
    """)

    # Permanent, Append-Only Audit Ledger (STRICTLY INSERT-ONLY)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        ml_risk_score REAL NOT NULL,
        raw_llm_reasoning TEXT,
        proposed_action TEXT,
        action_params TEXT,
        guardrail_status TEXT NOT NULL,
        policy_violation_reason TEXT,
        final_executed_action TEXT,
        execution_details TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers (id)
    )
    """)

    # Webhooks Dedup Table for Webhook Idempotency
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS webhooks_log (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        received_at TEXT NOT NULL,
        status TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def is_webhook_processed(event_id):
    """Webhook Idempotency: Returns True if webhook event_id was already ingested."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM webhooks_log WHERE event_id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def log_webhook_event(event_id, event_type, customer_id, status="INGESTED"):
    """Logs ingested webhook event to prevent duplicate processing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        cursor.execute("""
        INSERT INTO webhooks_log (event_id, event_type, customer_id, received_at, status)
        VALUES (?, ?, ?, ?, ?)
        """, (event_id, event_type, customer_id, now_iso, status))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists
    conn.close()

def seed_synthetic_data(force_recreate=True):
    """
    Populates database with realistic payment & merchant behavioral data:
    1. Healthy Subscriptions (Low churn risk)
    2. Involuntary Churn (Payment Mandate Failures & Card Expirations)
    3. Voluntary Churn (Merchant/User Inactivity & High Payment Drop-off)
    """
    init_db(force_recreate=force_recreate)
    conn = get_db_connection()
    cursor = conn.cursor()

    synthetic_customers = [
        {
            "id": "CUST-101",
            "name": "Apex Logistics India",
            "email": "payments@apexlogistics.in",
            "merchant_category": "SaaS Subscriptions",
            "mrr": 49999.00,
            "avg_transaction_value": 4999.00,
            "days_since_last_transaction": 1,
            "payment_failure_rate": 0.02,
            "failed_payment_count": 0,
            "mandate_status": "ACTIVE",
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-102",
            "name": "Nexus Cloud Infra",
            "email": "billing@nexuscloud.in",
            "merchant_category": "SaaS Subscriptions",
            "mrr": 19999.00,
            "avg_transaction_value": 1999.00,
            "days_since_last_transaction": 2,
            "payment_failure_rate": 0.05,
            "failed_payment_count": 0,
            "mandate_status": "ACTIVE",
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-201",
            "name": "FinTech Global Solutions",
            "email": "finance@fintechglobal.in",
            "merchant_category": "EdTech",
            "mrr": 79999.00,
            "avg_transaction_value": 7999.00,
            "days_since_last_transaction": 1,
            "payment_failure_rate": 0.45,
            "failed_payment_count": 3,
            "mandate_status": "FAILED_RETRY",
            "card_expiring_soon": 1,
            "has_discount": 0
        },
        {
            "id": "CUST-202",
            "name": "Vance Media House",
            "email": "accounts@vancemedia.in",
            "merchant_category": "D2C Brand",
            "mrr": 29999.00,
            "avg_transaction_value": 2999.00,
            "days_since_last_transaction": 3,
            "payment_failure_rate": 0.30,
            "failed_payment_count": 2,
            "mandate_status": "EXPIRING_SOON",
            "card_expiring_soon": 1,
            "has_discount": 0
        },
        {
            "id": "CUST-301",
            "name": "TechCorp India (Robert Sterling)",
            "email": "rsterling@techcorp.in",
            "merchant_category": "Enterprise SaaS",
            "mrr": 120000.00,
            "avg_transaction_value": 12000.00,
            "days_since_last_transaction": 32,
            "payment_failure_rate": 0.80,
            "failed_payment_count": 1,
            "mandate_status": "CANCELLED",
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-302",
            "name": "Bright Design Studio",
            "email": "amanda@brightdesign.in",
            "merchant_category": "Agency",
            "mrr": 9999.00,
            "avg_transaction_value": 999.00,
            "days_since_last_transaction": 45,
            "payment_failure_rate": 0.75,
            "failed_payment_count": 2,
            "mandate_status": "FAILED_RETRY",
            "card_expiring_soon": 0,
            "has_discount": 0
        },
        {
            "id": "CUST-303",
            "name": "HyperScale Ventures",
            "email": "leo@hyperscale.in",
            "merchant_category": "Gaming & Digital",
            "mrr": 65000.00,
            "avg_transaction_value": 6500.00,
            "days_since_last_transaction": 25,
            "payment_failure_rate": 0.60,
            "failed_payment_count": 1,
            "mandate_status": "ACTIVE",
            "card_expiring_soon": 0,
            "has_discount": 1
        }
    ]

    for c in synthetic_customers:
        cursor.execute("""
        INSERT OR REPLACE INTO customers (id, name, email, merchant_category, mrr, avg_transaction_value,
                              days_since_last_transaction, payment_failure_rate, failed_payment_count, 
                              mandate_status, card_expiring_soon, has_discount)
        VALUES (:id, :name, :email, :merchant_category, :mrr, :avg_transaction_value,
                :days_since_last_transaction, :payment_failure_rate, :failed_payment_count, 
                :mandate_status, :card_expiring_soon, :has_discount)
        """, c)

    conn.commit()
    conn.close()
    print(f"Successfully initialized database with {len(synthetic_customers)} synthetic merchants.")

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
    SELECT a.*, c.name as customer_name, c.email as customer_email, c.mrr, c.merchant_category
    FROM audit_log a
    JOIN customers c ON a.customer_id = c.id
    ORDER BY a.id DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    seed_synthetic_data(force_recreate=True)
