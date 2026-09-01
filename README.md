# Autonomous Fintech Retention Agent ("Retention Sentinel")

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask-green.svg)](https://flask.palletsprojects.com/)

An enterprise-grade autonomous retention agent for SaaS and Fintech platforms. The system explicitly separates **predictive intelligence** (churn likelihood ML classifier) from **agentic action** (LLM-driven retention strategies), governed by **deterministic, code-level financial guardrails** and an immutable audit ledger.

---

## 🏛️ Isolated 4-Layer Architecture

```
+-----------------------------------------------------------------------------------+
| 1. STORAGE & AUDIT LAYER (SQLite Database: fintech_agent.db)                     |
|    - Customers Table: Behavioral metrics, LTV, Idempotency status (processed=1)   |
|    - Audit_Log Table: Immutable ledger of risk scores, prompts, and policy checks  |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 2. PREDICTIVE ENGINE (Scikit-Learn ML Classifier)                                 |
|    - Evaluates: days_since_active, failed_payment_count, usage_drop_pct, etc.      |
|    - Output: Risk Score (0-100%). Triggers Agent ONLY if Risk Score >= 75%.         |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 3. REASONING ENGINE (LLM Tool Calling & Structured Schema Engine)                 |
|    - Generates retention strategy tool call (offer_discount, extend_trial, etc.)  |
|    - Persona: Retention Sentinel (maximize ARR retention, minimize leakage)       |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 4. EXECUTION & SAFETY INTERCEPTOR (Deterministic Financial Guardrails)            |
|    - Policy Rules: Max discount <=20%, Max trial <=14d, Idempotency lock, No stack|
|    - Outcome: APPROVED, BLOCKED (Policy Violation), or AUTO-REMEDIATED            |
|    - Ledger: Updates database & dispatches Mock Billing API calls                 |
+-----------------------------------------------------------------------------------+
```

---

## ✨ Key Enterprise Capabilities

1. **Explainability**: Every decision (ML score, LLM reasoning, policy verdict, API payload) is recorded in an append-only `Audit_Log` ledger table.
2. **Bounded Actions**: Hard code boundaries in `interceptor.py` mathematically restrict discounts (>20%) and trial extensions (>14 days), ignoring LLM overreach.
3. **Idempotency Protection**: A database-level `processed` state lock prevents duplicate interventions or discount stacking upon system restarts.

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/NagaVeeranna/bounded-recovery-agent.git
cd bounded-recovery-agent
pip install -r requirements.txt
```

### 2. Run Tests
```bash
python test_agent.py
```

### 3. Run CLI Batch Pipeline
```bash
python runner.py
```

### 4. Launch Interactive Web Dashboard
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 📄 License
MIT License
