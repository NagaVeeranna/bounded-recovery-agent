document.addEventListener("DOMContentLoaded", () => {
    loadDashboardData();
});

function switchTab(tabId) {
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(tab => tab.classList.remove("active"));

    const activeNav = document.querySelector(`.nav-item[onclick="switchTab('${tabId}')"]`);
    if (activeNav) activeNav.classList.add("active");

    const activeTab = document.getElementById(`tab-${tabId}`);
    if (activeTab) activeTab.classList.add("active");

    if (tabId === 'audit') loadAuditLogs();
    if (tabId === 'matrix') loadCustomers();
}

async function loadDashboardData() {
    await Promise.all([loadMetrics(), loadCustomers(), loadAuditLogs()]);
}

async function loadMetrics() {
    try {
        const res = await fetch("/api/metrics");
        const data = await res.json();
        if (data.success) {
            const m = data.metrics;
            document.getElementById("metric-total-customers").innerText = m.total_customers;
            document.getElementById("metric-at-risk-count").innerText = m.at_risk_count;
            document.getElementById("metric-mrr-at-risk").innerText = `₹${m.total_mrr_at_risk.toLocaleString('en-IN')}`;
            document.getElementById("metric-approved-count").innerText = m.approved_count;
            document.getElementById("metric-blocked-count").innerText = m.blocked_count;
        }
    } catch (err) {
        console.error("Failed to load metrics", err);
    }
}

async function loadCustomers() {
    const tbody = document.getElementById("customers-table-body");
    try {
        const res = await fetch("/api/customers");
        const data = await res.json();
        if (data.success) {
            tbody.innerHTML = "";
            data.customers.forEach(c => {
                const tr = document.createElement("tr");

                const score = c.risk_score || 0;
                let fillClass = "low";
                if (score >= 75) fillClass = "high";
                else if (score >= 40) fillClass = "medium";

                const isTriggered = score >= 75;
                const statusBadge = isTriggered 
                    ? `<span class="badge badge-blocked">AT RISK (>75%)</span>` 
                    : `<span class="badge badge-healthy">HEALTHY</span>`;

                const idempotencyBadge = c.processed == 1 
                    ? `<span class="badge badge-approved"><i class="fa-solid fa-lock"></i> Processed</span>` 
                    : `<span class="text-dim">Pending</span>`;

                let mandateBadge = `<span class="text-dim">${c.mandate_status}</span>`;
                if (c.mandate_status === 'FAILED_RETRY') {
                    mandateBadge = `<span class="badge badge-blocked">FAILED RETRY</span>`;
                } else if (c.mandate_status === 'EXPIRING_SOON') {
                    mandateBadge = `<span class="badge badge-remediated">EXPIRING SOON</span>`;
                } else if (c.mandate_status === 'ACTIVE') {
                    mandateBadge = `<span class="badge badge-approved">ACTIVE</span>`;
                }

                tr.innerHTML = `
                    <td>
                        <strong>${c.name}</strong><br>
                        <small class="text-muted">${c.id} • ${c.email}</small>
                    </td>
                    <td>
                        <strong>${c.merchant_category}</strong><br>
                        <span class="text-emerald">₹${c.mrr.toLocaleString('en-IN')}/mo</span>
                    </td>
                    <td>
                        <small>Last Txn: <strong>${c.days_since_last_transaction}d ago</strong></small> | 
                        <small>Fail Rate: <strong class="${c.payment_failure_rate > 0.3 ? 'text-rose' : ''}">${(c.payment_failure_rate * 100).toFixed(0)}%</strong></small><br>
                        <small>Failed Mandates: <strong>${c.failed_payment_count}</strong></small>
                    </td>
                    <td>${mandateBadge}</td>
                    <td>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill ${fillClass}" style="width: ${score}%"></div>
                        </div>
                        <strong>${score.toFixed(1)}%</strong>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${idempotencyBadge}</td>
                    <td>
                        <button class="btn btn-sm ${isTriggered ? 'btn-primary' : 'btn-outline'}" onclick="triggerSingleCustomer('${c.id}')">
                            <i class="fa-solid fa-play"></i> Run Agent
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Failed to load customers", err);
        tbody.innerHTML = `<tr><td colspan="8" class="text-rose text-center">Failed to load customer data.</td></tr>`;
    }
}

async function loadAuditLogs() {
    const tbody = document.getElementById("audit-table-body");
    try {
        const res = await fetch("/api/audit-logs");
        const data = await res.json();
        if (data.success) {
            tbody.innerHTML = "";
            if (data.audit_logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No audit ledger entries yet. Run the autonomous batch to generate records.</td></tr>`;
                return;
            }

            data.audit_logs.forEach(l => {
                const tr = document.createElement("tr");

                let verdictBadge = `<span class="badge badge-approved">APPROVED</span>`;
                if (l.guardrail_status === 'BLOCKED') {
                    verdictBadge = `<span class="badge badge-blocked">BLOCKED</span>`;
                } else if (l.guardrail_status === 'AUTO_REMEDIATED') {
                    verdictBadge = `<span class="badge badge-remediated">REMEDIATED</span>`;
                } else if (l.guardrail_status === 'API_ERROR_RETRY') {
                    verdictBadge = `<span class="badge badge-remediated">API RETRY</span>`;
                }

                const ts = new Date(l.timestamp).toLocaleTimeString();

                tr.innerHTML = `
                    <td>
                        <strong>#${l.id}</strong><br>
                        <small class="text-dim">${ts}</small>
                    </td>
                    <td>
                        <strong>${l.customer_name}</strong><br>
                        <small class="text-muted">${l.customer_id}</small>
                    </td>
                    <td><strong>${l.ml_risk_score.toFixed(1)}%</strong></td>
                    <td style="max-width: 260px; font-size: 12px; line-height: 1.4;">
                        <em>"${l.raw_llm_reasoning}"</em>
                    </td>
                    <td>
                        <code class="text-amber">${l.proposed_action}</code><br>
                        <small class="text-dim">${l.action_params}</small>
                    </td>
                    <td>${verdictBadge}</td>
                    <td style="max-width: 240px; font-size: 12px;">
                        ${l.policy_violation_reason ? `<span class="text-rose">${l.policy_violation_reason}</span>` : `<span class="text-emerald">${l.execution_details}</span>`}
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error("Failed to load audit logs", err);
    }
}

async function seedDatabase() {
    if (!confirm("Re-initialize SQLite database with fresh synthetic merchant personas?")) return;
    try {
        const res = await fetch("/api/seed", { 
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        alert(data.message);
        loadDashboardData();
    } catch (err) {
        alert("Failed to seed database: " + err);
    }
}

async function runBatchPipeline() {
    try {
        const res = await fetch("/api/process-all", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();
        alert("Autonomous batch execution completed!");
        loadDashboardData();
    } catch (err) {
        alert("Batch pipeline error: " + err);
    }
}

async function trainML() {
    try {
        const res = await fetch("/api/train-ml", { 
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        alert(data.message);
        loadCustomers();
    } catch (err) {
        alert("Train ML error: " + err);
    }
}

async function triggerSingleCustomer(customerId) {
    try {
        const res = await fetch(`/api/process-customer/${customerId}`, { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.success) {
            showTraceModal(customerId, data);
            loadDashboardData();
        }
    } catch (err) {
        alert("Trigger merchant error: " + err);
    }
}

function showTraceModal(customerId, data) {
    const modal = document.getElementById("trace-modal");
    const title = document.getElementById("modal-title");
    const content = document.getElementById("modal-content");

    title.innerText = `Execution Trace for ${customerId}`;
    
    const formattedJson = JSON.stringify(data, null, 2);
    content.innerHTML = `<pre style="color: #6366f1;">${formattedJson}</pre>`;
    modal.classList.remove("hidden");
}

function closeModal() {
    document.getElementById("trace-modal").classList.add("hidden");
}

function updateSimParams() {
    const action = document.getElementById("sim-action-name").value;
    document.getElementById("sim-params-discount").classList.add("hidden");
    document.getElementById("sim-params-trial").classList.add("hidden");

    if (action === "apply_retention_coupon" || action === "offer_discount") {
        document.getElementById("sim-params-discount").classList.remove("hidden");
    } else if (action === "extend_trial") {
        document.getElementById("sim-params-trial").classList.remove("hidden");
    }
}

async function runGuardrailSimulation(e) {
    e.preventDefault();
    const customerId = document.getElementById("sim-customer-id").value;
    const actionName = document.getElementById("sim-action-name").value;
    
    let params = {};
    if (actionName === "apply_retention_coupon" || actionName === "offer_discount") {
        params = {
            discount_percentage: parseFloat(document.getElementById("sim-param-pct").value),
            duration_months: parseInt(document.getElementById("sim-param-duration").value)
        };
    } else if (actionName === "trigger_smart_retry") {
        params = { gateway_priority: "HIGH" };
    } else if (actionName === "create_recovery_payment_link") {
        params = { amount_inr: 5000, expires_in_hours: 24 };
    } else if (actionName === "pause_subscription") {
        params = { duration_months: 3 };
    }

    const payload = {
        customer_id: customerId,
        action_name: actionName,
        parameters: params,
        simulate_idempotency_reset: true
    };

    try {
        const res = await fetch("/api/test-guardrail", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        const resContainer = document.getElementById("sim-result-container");
        const status = data.interceptor_result.guardrail_status;

        let statusText = `<span style="color:#10b981; font-weight:bold;">[VERDICT]: APPROVED</span>`;
        if (status === "BLOCKED") {
            statusText = `<span style="color:#ef4444; font-weight:bold;">[VERDICT]: BLOCKED (POLICY VIOLATION DETECTED)</span>`;
        }

        resContainer.innerHTML = `
${statusText}

----------------------------------------------------
PROPOSED TOOL CALL:
Action: ${actionName}
Params: ${JSON.stringify(params)}

INTERCEPTOR EVALUATION RESULT:
Guardrail Status: ${status}
Policy Violation: ${data.interceptor_result.policy_violation_reason || 'None (All rules passed)'}
Execution Details: ${JSON.stringify(data.interceptor_result.execution_details, null, 2)}
`;
    } catch (err) {
        alert("Simulation error: " + err);
    }
}

async function testIdempotencyRun() {
    const box = document.getElementById("idempotency-logs");
    box.innerHTML = `<span class="text-amber">Running duplicate pipeline trigger...</span>\n`;

    try {
        const res = await fetch("/api/process-all", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        const data = await res.json();

        const auditRes = await fetch("/api/audit-logs");
        const auditData = await auditRes.json();
        
        let logsText = "=== RECENT AUDIT LEDGER ENTRIES AFTER RE-TRIGGER ===\n\n";
        auditData.audit_logs.slice(0, 4).forEach(l => {
            logsText += `[Log #${l.id}] Merchant: ${l.customer_id} | Status: ${l.guardrail_status}\n`;
            logsText += `  Reason: ${l.policy_violation_reason || l.execution_details}\n\n`;
        });

        box.innerText = logsText;
        loadDashboardData();
    } catch (err) {
        box.innerText = "Idempotency test failed: " + err;
    }
}
