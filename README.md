# 🛡️ Retention Sentinel — Autonomous Fintech Retention Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask-green.svg)](https://flask.palletsprojects.com/)
[![ML: Scikit-Learn](https://img.shields.io/badge/ML-Scikit--Learn-orange.svg)](https://scikit-learn.org/)
[![Tests: PyTest](https://img.shields.io/badge/Tests-PyTest%207%2F7%20Passed-brightgreen.svg)](https://docs.pytest.org/)

An enterprise-grade autonomous retention agent designed for SaaS and Fintech platforms. The system strictly isolates **predictive intelligence** (ML churn classifier) from **agentic action** (LLM retention strategy generation), governed by **deterministic, code-level financial guardrails** and an immutable audit ledger.

---

## 🏛️ Isolated 4-Layer Architecture

```text
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
|    - Policy Rules: Max discount <=15%, Max trial <=14d, Idempotency lock, No stack|
|    - Outcome: APPROVED, BLOCKED (Policy Violation), or AUTO-REMEDIATED            |
|    - Ledger: Updates database & dispatches Mock Billing API calls                 |
+-----------------------------------------------------------------------------------+
```

---

## 📋 Architectural Component Mapping

| Component | Target Responsibility | Key Implementation & Validation Points |
| :--- | :--- | :--- |
| [`predictor.py`](file:///d:/Recovery%20-Agent/predictor.py) | **Tabular ML Risk Engine** | Trains Random Forest classifier on synthetic behavioral data. Predicts churn risk scores (0–100%). Filters and triggers ONLY accounts $\ge 75\%$ risk score. |
| [`agent.py`](file:///d:/Recovery%20-Agent/agent.py) | **Reasoning Brain** | Formulates customer context and queries LLM / structured schema engine to return JSON tool-call payloads (`offer_discount`, `extend_trial`, `pause_subscription`, etc.). |
| [`interceptor.py`](file:///d:/Recovery%20-Agent/interceptor.py) | **Safety & Bounded Logic** | Intercepts agent actions before execution; enforces policy cap ($\le 15\%$), blocks stacked discounts, checks 6-month LTV ratio cap ($50\%$), and rejects invalid tool names with `INVALID_TOOL_NAME`. |
| [`mock_api.py`](file:///d:/Recovery%20-Agent/mock_api.py) | **Tool Implementations** | Emulates Stripe/payment gateway mutations (discount applications, trial extensions, subscription pauses) with rate-limit (`HTTP 429`) & 500 error retries. |
| [`database.py`](file:///d:/Recovery%20-Agent/database.py) | **Immutable Audit Ledger** | SQLite database with append-only `Audit_Log` ledger recording customer metrics, raw reasoning prompts, policy verdicts (`APPROVED`, `BLOCKED`, `AUTO_REMEDIATED`), and `processed = 1` state locks. |
| [`runner.py`](file:///d:/Recovery%20-Agent/runner.py) | **Pipeline Orchestration** | Batch execution runner iterating over customer profiles: `Predictor` $\rightarrow$ `Agent` $\rightarrow$ `Interceptor` $\rightarrow$ `Mock API` $\rightarrow$ `Database Audit Ledger`. |
| [`app.py`](file:///d:/Recovery%20-Agent/app.py) + **UI** | **Demonstration Dashboard** | Flask web app serving a Glassmorphic dashboard at **`http://127.0.0.1:5000`** displaying live risk scores, explainability audit ledger, policy testing simulator, and idempotency tests. |
| [`test_agent.py`](file:///d:/Recovery%20-Agent/test_agent.py) | **Safety & Flow Verification** | Full PyTest suite covering normal recovery flows, rate-limit retries, excessive prompt blocks, invalid tool rejection, and idempotency protection. |

---

## 🔒 Enterprise Safety & Verification Checklist

1. **Dependency Sanity**:
   - Lean, CPU-friendly dependencies in `requirements.txt`: `scikit-learn`, `pandas`, `numpy`, `Flask`, `flask-cors`, `requests`, `google-genai`, `pytest`.
2. **Guardrail Enforcement in `interceptor.py`**:
   - **Discount Cap**: Maximum allowed discount strictly bounded at **15%** (`MAX_DISCOUNT_PERCENTAGE`).
   - **Double-Discount Guard**: Rejects discount stacking if `customer.has_discount == 1`.
   - **Invalid Tool Protection**: Rejects unauthorized or out-of-scope tool calls with `INVALID_TOOL_NAME`.
   - **Full Ledgering**: Every verdict (`APPROVED`, `BLOCKED`, `AUTO_REMEDIATED`, `API_ERROR_RETRY`) is committed to the append-only `Audit_Log`.
3. **Idempotency & System Restarts in `runner.py`**:
   - Once an account is processed, `processed = 1` is committed to the database. Re-running the batch runner or restarting the server returns `IDEMPOTENCY_VIOLATION`, preventing double-discounting or duplicate interventions.
4. **API Failure Resilience**:
   - Emulates Stripe gateway rate limits (`HTTP 429`) or server errors (`HTTP 500`) and falls back gracefully with retry logging (`API_ERROR_RETRY`) without crashing the pipeline.

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/NagaVeeranna/bounded-recovery-agent.git
cd bounded-recovery-agent
pip install -r requirements.txt
```

### 2. Run Automated PyTest Verification Suite
```bash
pytest test_agent.py
```
*Expected Output:* `7 passed in 3.79s`

### 3. Run Autonomous CLI Pipeline
```bash
python runner.py
```

### 4. Launch Interactive Web Dashboard
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser to access the interactive Glassmorphic dashboard.

---

## 🌐 Web Dashboard Features (`http://127.0.0.1:5000`)

- **Predictive Risk Matrix**: Real-time view of customer churn scores, behavioral drop-off metrics, and risk status indicators.
- **Explainability Audit Ledger**: Searchable, 100% transparent history displaying ML risk scores, raw LLM reasoning, interceptor verdicts, and execution logs.
- **Guardrail Policy Simulator**: Interactive sandbox allowing users to test custom payloads against policy boundaries (e.g., testing 30% discount requests or unauthorized tool names).
- **Idempotency Safety Simulator**: One-click verification proving duplicate runs on processed accounts are mathematically blocked.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/customers` | `GET` | Fetches all customer profiles, behavioral metrics, and ML risk scores. |
| `GET /api/audit-logs` | `GET` | Returns full append-only audit ledger history. |
| `GET /api/metrics` | `GET` | Returns system KPIs (Total MRR at risk, approved vs blocked actions, policy limits). |
| `POST /api/seed` | `POST` | Re-seeds SQLite database with fresh synthetic customer personas. |
| `POST /api/process-all` | `POST` | Triggers the autonomous retention pipeline across all customer accounts. |
| `POST /api/process-customer/<id>` | `POST` | Runs the agent pipeline on a single target customer with full JSON execution trace. |
| `POST /api/test-guardrail` | `POST` | Simulates an arbitrary tool call payload against the guardrail interceptor. |

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for details.
