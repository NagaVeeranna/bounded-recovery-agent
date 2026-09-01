# 🛡️ Retention Sentinel — Bounded Autonomous Retention Agent
### *Enterprise AI Agent for Subscriptions & Payment Gateways*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask-green.svg)](https://flask.palletsprojects.com/)
[![ML: Scikit-Learn](https://img.shields.io/badge/ML-Scikit--Learn-orange.svg)](https://scikit-learn.org/)
[![Validation: Pydantic](https://img.shields.io/badge/Validation-Pydantic%20v2-red.svg)](https://docs.pydantic.dev/)
[![Tests: PyTest](https://img.shields.io/badge/Tests-PyTest%209%2F9%20Passed-brightgreen.svg)](https://docs.pytest.org/)
[![CI/CD: GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](https://github.com/features/actions)

An enterprise-grade autonomous churn recovery agent designed for **Subscriptions & Payment Gateways**. The system strictly isolates **predictive intelligence** (ML churn classifier) from **agentic action** (LLM dunning strategies), governed by **deterministic, code-level financial guardrails**, **Pydantic schema validation**, **prompt injection defense**, and an immutable audit ledger.

---

## 🏛️ Isolated 4-Layer Architecture

```text
+-----------------------------------------------------------------------------------+
| 1. STORAGE & AUDIT LAYER (SQLite Database: fintech_agent.db)                     |
|    - Customers Table: Merchant metrics, GMV, Mandate status, Idempotency (processed=1)|
|    - Audit_Log Table: Immutable ledger of risk scores, prompts, and policy checks  |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 2. PREDICTIVE ENGINE (Scikit-Learn ML Classifier)                                 |
|    - Evaluates: payment_failure_rate, days_since_last_transaction, GMV, etc.      |
|    - Output: Risk Score (0-100%). Triggers Agent ONLY if Risk Score >= 75%.         |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 3. REASONING ENGINE (LLM Tool Calling + Prompt Sanitizer + Pydantic Schema)       |
|    - Generates retention tool calls (trigger_smart_retry, enable_upi_autopay, etc.)|
|    - Persona: Retention Sentinel (maximize GMV retention, minimize leakage)        |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| 4. EXECUTION & SAFETY INTERCEPTOR (Deterministic Financial Guardrails)            |
|    - Policy Rules: Max coupon <=15%, Max trial <=14d, Idempotency lock, LTV cap   |
|    - Outcome: APPROVED, BLOCKED (Policy Violation), or AUTO-REMEDIATED            |
|    - Ledger: Updates database & dispatches MockBillingAPI calls                  |
+-----------------------------------------------------------------------------------+
```

---

## 🧠 LLM-Specific Principles (Trust & Safety Architecture)

- **Separation of Reasoning and Action**: The LLM generates a structured tool recommendation, but **never executes it directly**. The Interceptor validates and enforces hard financial policies before any gateway mutation occurs.
- **Prompt-Injection Defense**: Pre-processor sanitizer (`sanitize_merchant_input`) strips suspicious injection tokens, system override attempts, and HTML tags from merchant inputs before injecting into system prompts.
- **Pydantic Schema Validation**: Second-pass Pydantic validator (`ReasoningPayload`) guarantees 100% JSON schema conformity. Invalid LLM outputs fall back safely without crashing.
- **Few-Shot Prompt Engineering**: Includes explicit few-shot examples in the system prompt for consistent tool selection across involuntary vs voluntary churn scenarios.
- **Deterministic Guardrails Over LLM Outputs**: Financial limits ($\le 15\%$ coupon, double-coupon block, LTV caps) are hardcoded in `config.py` and `interceptor.py`, not left to probabilistic LLM prompts.
- **Full Audit Ledger**: Immutable append-only `Audit_Log` commits every prompt, raw LLM reasoning, risk score, and interceptor verdict for post-hoc compliance and explainability.
- **Idempotency & Retry Resilience**: Database state lock (`processed = 1`) prevents double-firing actions; automatic retry handling (`API_ERROR_RETRY`) handles HTTP 429/500 gateway errors.

---

## 🛠️ Software Engineering Principles (Production-Ready Code)

- **Modular, Layered Architecture**: `config.py`, `database.py`, `predictor.py`, `agent.py`, `interceptor.py`, `mock_api.py`, `runner.py`, `app.py`. Each module has a single responsibility.
- **Centralized Configuration Management**: Config parameters (`MAX_DISCOUNT_PERCENTAGE`, `RISK_TRIGGER_THRESHOLD`, secrets) managed cleanly in `config.py`.
- **Test-Driven Verification**: 9/9 PyTest tests covering normal flows, prompt injection defense, UPI AutoPay, rate limits, invalid tools, and idempotency.
- **Payment Failure Webhook Integration**: Endpoint `POST /api/webhooks/payment-failed` simulates receiving `payment.failed` gateway webhook events to trigger instant recovery.
- **CI/CD Automation**: GitHub Actions workflow (`.github/workflows/test.yml`) automatically executes test suites on every commit.

---

## 📋 Architectural Component Mapping

| Component | Target Responsibility | Key Implementation & Validation Points |
| :--- | :--- | :--- |
| [`config.py`](file:///d:/Recovery%20-Agent/config.py) | **Configuration Management** | Centralized bounds (Max discount 15%, max trial 14d, LTV ratio 50%, 75% trigger threshold). |
| [`predictor.py`](file:///d:/Recovery%20-Agent/predictor.py) | **ML Churn Risk Engine** | Trains Random Forest classifier on payment failure rates, inactivity, and GMV. Outputs scores 0–100%. |
| [`agent.py`](file:///d:/Recovery%20-Agent/agent.py) | **Reasoning Brain + Sanitizer** | Prompt injection pre-processor, Few-Shot prompting, Gemini API integration, Pydantic schema validation. |
| [`interceptor.py`](file:///d:/Recovery%20-Agent/interceptor.py) | **Safety Interceptor** | Evaluates tool calls against hard bounds; blocks excessive coupons (>15%), double coupons, and unknown tools. |
| [`mock_api.py`](file:///d:/Recovery%20-Agent/mock_api.py) | **Billing & Gateway APIs** | Smart Retry, UPI AutoPay mandate setup, Payment Links, Subscription Coupons, WhatsApp Reminders. |
| [`database.py`](file:///d:/Recovery%20-Agent/database.py) | **Immutable Audit Ledger** | SQLite database with append-only `Audit_Log` ledger recording all risk scores, prompts, and verdicts. |
| [`runner.py`](file:///d:/Recovery%20-Agent/runner.py) | **Pipeline Orchestration** | Batch execution runner iterating over merchant accounts with formatted CLI logs. |
| [`app.py`](file:///d:/Recovery%20-Agent/app.py) + **UI** | **Dashboard & Webhooks** | Flask web app serving Glassmorphic UI at **`http://127.0.0.1:5000`** & `POST /api/webhooks/payment-failed`. |
| [`test_agent.py`](file:///d:/Recovery%20-Agent/test_agent.py) | **Safety Verification Suite** | 9/9 PyTest suite validating prompt injection, UPI AutoPay, webhook triggers, rate limits, and idempotency. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Installation

```bash
git clone https://github.com/NagaVeeranna/bounded-recovery-agent.git
cd bounded-recovery-agent
pip install -r requirements.txt
```

### 2. Run PyTest Verification Suite
```bash
pytest test_agent.py
```
*Expected Output:* `9 passed in 3.75s`

### 3. Run Autonomous CLI Pipeline
```bash
python runner.py
```

### 4. Launch Merchant Web Dashboard
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 📡 REST API & Webhook Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/customers` | `GET` | Fetches all merchant profiles, payment metrics, and ML risk scores. |
| `GET /api/audit-logs` | `GET` | Returns full append-only audit ledger history. |
| `GET /api/metrics` | `GET` | Returns system KPIs (Total GMV at risk in ₹ INR, approved vs blocked actions). |
| `POST /api/webhooks/payment-failed` | `POST` | **Payment Webhook**: Simulates `payment.failed` event and triggers recovery. |
| `POST /api/process-all` | `POST` | Triggers the autonomous retention pipeline across all merchant accounts. |
| `POST /api/process-customer/<id>` | `POST` | Runs the agent pipeline on a single target merchant with full JSON execution trace. |
| `POST /api/test-guardrail` | `POST` | Simulates an arbitrary tool call payload against the guardrail interceptor. |

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for details.
