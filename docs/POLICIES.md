# Platform Safety & Recovery Policies (`POLICIES.md`)

This document defines the 12 deterministic safety guardrails enforced by the `PolicyEngine` in `backend/app/policy_engine.py`.

---

## Architectural Principles

1. **Deterministic Safety Precedence**: Policies execute **strictly prior to payment execution** (Rule 12).
2. **Zero LLM Override**: LLM suggestions, prompt injections, or external override flags cannot bypass policy rules (Rule 11).
3. **Comprehensive Audit Logging**: Every policy denial is recorded with rule ID, severity, timestamp, and transaction context (Rule 10).

---

## Policy Registry

| Rule ID | Rule Name | Outcome | Severity | Description |
| :--- | :--- | :--- | :--- | :--- |
| **POL-001** | Never Retry Success | `DENY` | `CRITICAL` | Under no circumstances may a recovery action be executed against a transaction that has already reached `SUCCESS`. Prevents double charges. |
| **POL-002** | Never Retry Duplicate | `DENY` | `CRITICAL` | Duplicate payments detected via idempotency keys or temporal heuristics are immediately halted (`STOP`). |
| **POL-003** | Block High-Risk Auto-Recovery | `ESCALATE` | `CRITICAL` | Automated payment retries, method switches, and messages are prohibited when `risk_score > 0.85` or category is `RISK`. Must escalate to risk analysts. |
| **POL-004** | Enforce Retry Limits | `DENY` | `HIGH` | Maximum retry attempts per transaction (e.g. 2 for immediate retry, 3 for scheduled retry) are strictly capped. |
| **POL-005** | Enforce Retry Cooldown | `WAIT` | `MEDIUM` | Retries cannot be dispatched faster than the minimum cooldown window (60s for immediate, 300s for scheduled). |
| **POL-006** | Escalate High-Value Risky | `ESCALATE` | `HIGH` | High-value payments (\(\ge\) ₹50,000) with elevated risk scores (\(\ge 0.50\)) require manual human supervisor clearance. |
| **POL-007** | Wait on Pending Payments | `WAIT` | `HIGH` | Payments pending gateway/bank settlement must not be re-attempted. The system polls gateway status instead. |
| **POL-008** | Stop on Invalid State | `DENY` | `CRITICAL` | Transactions with unrecognized, corrupted, or incompatible lifecycle states are immediately stopped. |
| **POL-009** | Respect Customer DND / Opt-Out | `DENY` | `MEDIUM` | Recovery messages (SMS, WhatsApp, email) must not be dispatched to customers with active DND or communication opt-out flags. |
| **POL-010** | Audit Every Denial | `N/A` | `HIGH` | Every denial creates a persistent audit event with rule ID, reason, and severity. |
| **POL-011** | LLM Cannot Bypass Policy | `DENY` | `CRITICAL` | Explicit guardrail preventing prompt injection, bypass parameters, or LLM output from superseding safety rules. |
| **POL-012** | Policy Runs Before Execution | `N/A` | `CRITICAL` | Pre-execution gatekeeper; no action reaches payment gateways without policy approval. |

---

## Policy Outcomes

- **`ALLOW`**: The candidate action complies with all guardrails and is permitted for execution.
- **`DENY`**: The candidate action violates a safety rule and is strictly rejected. Action is rerouted to `STOP`.
- **`WAIT`**: The candidate action cannot be executed immediately (e.g. active cooldown, pending settlement). Execution is deferred.
- **`ESCALATE`**: The candidate action poses risk or value anomalies that require manual human operations clearance.
