<div align="center">

# 🛡️ Retention Sentinel
### *Bounded Autonomous Churn Recovery & Dunning Agent*

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Framework Flask](https://img.shields.io/badge/Flask-2.3%2B-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML%20Engine-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://scikit-learn.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-Schema%20Safety-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![PyTest Passed](https://img.shields.io/badge/PyTest-9%2F9%20Passed-2EA44F?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![License MIT](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](https://opensource.org/licenses/MIT)

---

**Retention Sentinel** is an enterprise-grade autonomous churn recovery system designed for **Subscription Platforms & Payment Gateways**.  
It strictly decouples **Predictive Machine Learning** (ML risk classification) from **Agentic Reasoning** (LLM dunning strategies), strictly bounded by **Deterministic Code-Level Financial Guardrails**, **Pydantic Schema Validation**, **Prompt-Injection Defense**, and an **Immutable Audit Ledger**.

</div>

---

> [!IMPORTANT]
> **Separation of Reasoning & Action**: The LLM recommends structured tool actions but **cannot execute mutations directly**. Every proposed action passes through a deterministic Safety Interceptor enforcing financial caps (e.g., maximum 15% coupon, double-discount prevention, and LTV ratio checks) before touching billing APIs.

---

## 🏛️ System Architecture

```text
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 1. STORAGE & AUDIT LEDGER (SQLite: fintech_agent.db)                              │
│    - Customers Table : Merchant metrics, GMV, Mandate status, Idempotency lock     │
│    - Audit_Log Table : Immutable record of prompts, scores, and policy verdicts    │
└───────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 2. PREDICTIVE ENGINE (Scikit-Learn ML Classifier)                                 │
│    - Features: failure_rate, days_inactive, mandate_status, transaction_value     │
│    - Output  : Risk Score (0-100%). Triggers LLM agent ONLY if Risk Score >= 75%   │
└───────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 3. REASONING ENGINE (LLM Tool Calling + Prompt Sanitizer + Pydantic Schema)       │
│    - Input Sanitizer: Strips prompt injection tokens and instruction overrides     │
│    - Schema Validation: Pydantic second-pass model guarantees 100% JSON structure  │
└───────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 4. SAFETY INTERCEPTOR & EXECUTION LAYER (Deterministic Guardrails)                │
│    - Financial Bounds: Max coupon <= 15%, Max trial <= 14d, LTV ratio <= 50%       │
│    - Action Verdict : APPROVED, BLOCKED (Policy Violation), or AUTO-REMEDIATED     │
│    - Mock Billing API: Dispatches Smart Retry, UPI AutoPay, Payment Links          │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 Key Architectural Principles

### 🧠 LLM Trust & Safety
- **Prompt Injection Pre-Processor**: `sanitize_merchant_input()` strips system override tokens (`SYSTEM:`, `Ignore previous instructions`, HTML/script tags) prior to prompt insertion.
- **Pydantic Schema Conformity**: Second-pass validator (`ReasoningPayload`) guarantees strict JSON output structure. Malformed outputs gracefully revert to safe fallback rules.
- **Few-Shot System Prompting**: Pre-loaded with contextual few-shot scenarios for accurate tool selection across involuntary vs. voluntary churn.
- **Deterministic Guardrails**: Hard policy limits ($\le 15\%$ coupon, double-discount prevention, LTV caps) are code-enforced in `config.py` and `interceptor.py`, eliminating reliance on probabilistic prompts.
- **Immutable Audit Trail**: Append-only `audit_log` commits raw prompts, ML scores, interceptor verdicts, and execution logs for complete regulatory compliance.
- **Idempotency Lock**: Database state lock (`processed = 1`) mathematically blocks duplicate interventions on the same account across pipeline restarts.

### ⚙️ Software Engineering Standards
- **Modular Component Design**: Decoupled modules (`config`, `database`, `predictor`, `agent`, `interceptor`, `mock_api`, `runner`, `app`).
- **Centralized Configuration**: Environment variable overrides managed via `config.py`.
- **Payment Failure Webhook**: Endpoint `POST /api/webhooks/payment-failed` handles gateway `payment.failed` events to trigger real-time recovery workflows.
- **Test-Driven Safety Suite**: 9/9 PyTest suite covering normal recovery, rate limits, invalid tools, prompt injections, and idempotency.
- **Automated CI/CD**: GitHub Actions workflow (`.github/workflows/test.yml`) executes full test suite on push/pull requests.

---

## 📂 Component Sitemap

| File | Module | Target Responsibility |
| :--- | :--- | :--- |
| [`config.py`](file:///d:/Recovery%20-Agent/config.py) | **Configuration** | Centralized parameter bounds (Max discount 15%, max trial 14d, 75% risk threshold). |
| [`database.py`](file:///d:/Recovery%20-Agent/database.py) | **Audit Ledger** | SQLite database managing `customers` table and append-only `audit_log` table. |
| [`predictor.py`](file:///d:/Recovery%20-Agent/predictor.py) | **Predictive Engine** | Random Forest classifier predicting churn risk (0–100%) based on payment behaviors. |
| [`agent.py`](file:///d:/Recovery%20-Agent/agent.py) | **Reasoning Brain** | Sanitizes merchant inputs, generates tool calls, and validates via Pydantic schema. |
| [`interceptor.py`](file:///d:/Recovery%20-Agent/interceptor.py) | **Safety Interceptor** | Evaluates proposed actions against deterministic financial rules and dispatches API calls. |
| [`mock_api.py`](file:///d:/Recovery%20-Agent/mock_api.py) | **Billing Gateway API** | Emulates Smart Retry, UPI AutoPay setup, Payment Links, Coupons, and WhatsApp reminders. |
| [`runner.py`](file:///d:/Recovery%20-Agent/runner.py) | **Pipeline Runner** | CLI batch runner orchestrating ML prediction $\rightarrow$ Agent reasoning $\rightarrow$ Interceptor execution. |
| [`app.py`](file:///d:/Recovery%20-Agent/app.py) | **Flask Server** | Web application serving dashboard API endpoints and Webhook receiver. |
| [`templates/index.html`](file:///d:/Recovery%20-Agent/templates/index.html) | **Glassmorphic UI** | Responsive web dashboard displaying risk matrix, audit ledger, and policy simulator. |
| [`test_agent.py`](file:///d:/Recovery%20-Agent/test_agent.py) | **Verification Suite** | 9/9 PyTest test cases verifying safety barriers, prompt injection, and idempotency. |

---

## ⚡ Quick Start

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/NagaVeeranna/bounded-recovery-agent.git
cd bounded-recovery-agent
pip install -r requirements.txt
```

### 2. Run Test Suite (9/9 PyTest)
Verify system safety barriers and schema models:
```bash
pytest test_agent.py
```
*Output:* `9 passed in 3.75s`

### 3. Run Autonomous CLI Pipeline
Orchestrate batch churn recovery in terminal:
```bash
python runner.py
```

### 4. Launch Web Dashboard
Start the local development server:
```bash
python app.py
```
Access the dashboard at **`http://127.0.0.1:5000`**.

---

## 📡 REST API & Webhook Specification

| Route | Method | Payload / Description |
| :--- | :---: | :--- |
| `GET /api/customers` | `GET` | Fetches all merchant profiles, payment metrics, and ML risk scores. |
| `GET /api/audit-logs` | `GET` | Returns full append-only explainability audit ledger. |
| `GET /api/metrics` | `GET` | Returns high-level KPIs (Total GMV at risk in ₹ INR, approved vs. blocked count). |
| `POST /api/webhooks/payment-failed` | `POST` | **Payment Webhook**: Simulates `payment.failed` event & triggers recovery workflow. |
| `POST /api/process-all` | `POST` | Runs autonomous retention pipeline across all accounts. |
| `POST /api/process-customer/<id>` | `POST` | Executes pipeline for a single merchant with detailed execution trace. |
| `POST /api/test-guardrail` | `POST` | Interactive endpoint testing custom tool payloads against safety guardrails. |

---

> [!TIP]
> **Interactive Policy Simulator**: Navigate to the **Dunning Policy Simulator** tab in the web dashboard to test sending unauthorized tool calls (e.g. 30% coupon) and observe the Interceptor blocking the action in real time.

---

## 📄 License
This project is open-source software licensed under the **[MIT License](LICENSE)**.
