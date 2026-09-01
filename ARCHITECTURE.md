# RazorRecover AI Architecture

## 1. Project Overview

RazorRecover AI is a fintech AI hackathon project that models autonomous revenue recovery for failed payments and abandoned checkouts. The system uses synthetic payment and checkout data only, built to demonstrate realistic workflows without using real Razorpay production data or live payment rails.

The goal is to detect revenue risk, predict recoverability, explain root cause, choose a safe recovery action, run the action in a payment simulator, monitor the result, and report net recovered value.

## 2. Critical Constraints

### Hard constraints
- No private Razorpay production data, internal APIs, or payment infrastructure access.
- No real money movement.
- Synthetic data only.
- No Docker dependency.
- Frontend must be deployable to Vercel.
- No long-running background workers.
- No GPU dependency.
- No Redis unless absolutely necessary.
- No WebSockets required.
- No local persistent storage requirement.
- No model training during API requests.

### Architectural interpretation
- Payment execution is explicitly simulated.
- The system is designed so a real provider integration can be substituted later behind the same interfaces.
- The LLM is advisory only; deterministic safety policies always gate actual execution.

## 3. High-level System Design

RazorRecover AI is organized as a layered decision system:

1. Synthetic event generation creates realistic failed payment and checkout abandonment scenarios.
2. Event ingestion normalizes and validates events into a canonical schema.
3. Context retrieval assembles payment, customer, order, and merchant context.
4. Root cause classification assigns a primary failure type and category.
5. ML prediction estimates recovery probability, customer behavior, and risk.
6. Action-level value estimation computes expected revenue recovery for each action.
7. Policy engine blocks unsafe or non-permissible actions.
8. Agentic orchestration selects the next best recovery action with explanation.
9. Payment simulator executes the action deterministically and records the result.
10. Result monitoring evaluates the outcome and decides whether to retry, escalate, or stop.
11. Audit and dashboard layers provide observability and financial reporting.

## 4. System Components

### 4.1 Synthetic Data Layer
Purpose:
- Generate realistic payment and checkout events for testing, demos, and benchmarking.
- Avoid dependence on sensitive production data.

Components:
- synthetic data generator
- customer profiles and risk classes
- payment instrument profiles
- checkout session states
- merchant and order metadata
- scenario templates for failures and recoveries

### 4.2 Event Ingestion Service
Purpose:
- Accept incoming events from synthetic pipelines, APIs, or future integrations.
- Standardize payloads for downstream processing.

Responsibilities:
- validation
- normalization
- deduplication checks
- event metadata tagging
- queue-free synchronous processing for hackathon constraints

### 4.3 Context Retrieval and Enrichment
Purpose:
- Build a complete picture of the failed interaction before making a recovery recommendation.

Included context:
- customer profile and historical behavior
- payment context and attempted methods
- order characteristics and value
- merchant policy and risk settings
- prior recovery attempts
- failure frequency and timings

### 4.4 Classification and Root Cause Engine
Purpose:
- Convert a raw failure into structured causes and business-ready explanations.

Classification outputs:
- failure type (for example: BANK_UNAVAILABLE, CARD_DECLINED, OTP_FAILURE)
- failure category (for example: TEMPORARY, AUTHENTICATION, BANK, TECHNICAL)
- probable root cause
- confidence score

### 4.5 Predictive ML Layer
Purpose:
- Estimate recoverability and risk using interpretable tabular ML models.

Models and outputs:
- recovery probability
- risk prediction
- customer churn/abandonment likelihood
- action-specific recovery probability
- expected recovery value

Tech stack:
- pandas
- scikit-learn
- XGBoost

Model training:
- offline training on synthetic datasets
- saved model artifacts or deterministic serialized pipeline
- no training on request

### 4.6 Deterministic Policy Engine
Purpose:
- Guarantee the LLM never bypasses business, fraud, and safety rules.

Policy categories:
- retry limits
- duplicate payment protection
- fraud and risk blocks
- status-transition restrictions
- action availability for failure types
- escalation rules and stop conditions
- max exposure thresholds

Important rule:
- The agent may recommend an action, but the policy engine decides whether it is executable.

### 4.7 AI Agent / Orchestration Layer
Purpose:
- Provide contextual reasoning, natural-language explanation, and orchestration.

Responsibilities:
- interpret context, root cause, and ML outputs
- select a recovery action among safe options
- produce explainable reasoning traces
- delegate execution to deterministic simulator tools only

Tech stack:
- LangGraph
- configurable LLM provider
- deterministic fallback when no LLM is available

Design principle:
- LLM output is not trusted to execute payment transitions directly.
- Agent chooses from a constrained tool set and must pass through policy validation.

### 4.8 Payment Simulator
Purpose:
- Simulate the outcome of a recovery action in a controlled, deterministic environment.

Simulator responsibilities:
- payment state transitions
- retry simulation
- payment method switching simulation
- message send simulation
- schedule retry simulation
- escalation handling
- outcome scoring
- audit generation

This layer is intentionally replaceable by a real provider integration later.

### 4.9 Result Monitoring and Recovery Decision Loop
Purpose:
- Determine whether the recovery action succeeded, partially succeeded, or should end.

Loop stages:
- monitor post-action status
- classify outcome
- compute recovered value
- decide next action or stop
- log reasoning, policy decisions, and final state

### 4.10 Audit Trail and Dashboard
Purpose:
- Maintain a transparent, explainable record of actions and outcomes for demo and evaluation.

Outputs:
- recovery decision logs
- policy decision entries
- event timeline
- baseline vs AI comparison
- revenue recovered metrics
- batch simulation summaries

## 5. Core Execution Flow

1. Synthetic Event
2. Event Ingestion
3. Context Retrieval
4. Root Cause Classification
5. ML Prediction
6. Action Probability
7. Expected Value
8. Policy Check
9. Agent Decision
10. Simulated Action
11. Result Monitoring
12. Recovery / Next Action / Stop / Escalate
13. Audit Log
14. Dashboard

## 6. Data Model Sketch

### PaymentEvent
- event_id
- event_type
- merchant_id
- order_id
- customer_id
- amount
- currency
- payment_method
- attempt_count
- status
- failure_type
- failure_category
- timestamp
- metadata

### CustomerContext
- customer_id
- risk_score
- preferred_payment_method
- historical_declines
- churn_likelihood
- previous_recovery_attempts
- engagement_score

### PaymentContext
- order_value
- payment_flow_stage
- gateway_response_code
- previous_retry_count
- method_availability
- auth_attempts
- fraud_flags

### RecoveryDecision
- decision_id
- event_id
- recommendation
- action
- policy_status
- reason
- confidence
- expected_recovered_value
- executed
- result

## 7. Failure Taxonomy

### Failure Types
- GATEWAY_TIMEOUT
- BANK_UNAVAILABLE
- INSUFFICIENT_FUNDS
- CARD_DECLINED
- CARD_EXPIRED
- OTP_FAILURE
- AUTH_TIMEOUT
- HIGH_RISK
- CUSTOMER_ABANDONED
- PAYMENT_PENDING
- DUPLICATE_PAYMENT
- ORDER_CREATION_FAILED

### Failure Categories
- TEMPORARY
- CUSTOMER
- PAYMENT_METHOD
- AUTHENTICATION
- BANK
- TECHNICAL
- RISK
- ABANDONMENT
- PENDING
- DUPLICATE
- MERCHANT

## 8. Recovery Actions

- RETRY_PAYMENT
- SWITCH_PAYMENT_METHOD
- SEND_RECOVERY_MESSAGE
- SCHEDULE_RETRY
- ESCALATE
- STOP

## 9. Safety and Security Controls

- All actions must pass policy validation before execution.
- The simulator is a controlled environment; no real financial transactions occur.
- All sensitive fields are treated as synthetic and non-production.
- Audit logs capture decision path, rationale, and policy checks.
- Action execution must be deterministic and traceable.
- The agent cannot bypass restrictions by directly mutating payment state.

## 10. ML and Agent Division of Responsibility

### ML responsibilities
- recovery probability
- risk prediction
- customer behavior prediction
- action-specific expected outcomes

### LLM / agent responsibilities
- orchestration
- contextual reasoning
- root-cause explanation
- tool selection
- natural-language explanations

### Deterministic code responsibilities
- payment state transitions
- safety policies
- retry limits
- duplicate protection
- fraud restrictions
- action execution
- audit recording

## 11. Deployment Architecture

### Frontend
- Next.js + TypeScript + Tailwind CSS
- Recharts for charts
- Deployed to Vercel
- API calls hit a backend endpoint or mock demo API during hackathon staging

### Backend
- Python + FastAPI + Pydantic + SQLAlchemy
- Can be deployed to a managed Python host such as Render, Azure App Service, or similar
- No Docker required

### Database
- PostgreSQL-compatible managed database
- Used for event archive, simulation results, audit logs, and dashboard queries

### Simulation mode
- local dev mode may use SQLite or a lightweight in-memory store for demo/testing
- production-like environment should use PostgreSQL-compatible managed storage

## 12. Repository Structure

```text
razorrecover-ai/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── tailwind.config.js
├── backend/
│   ├── app/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── policies/
│   ├── simulator/
│   ├── tests/
│   ├── main.py
│   ├── requirements.txt
│   └── pyproject.toml
├── data/
│   ├── synthetic/
│   └── notebooks/
├── ml/
│   ├── models/
│   ├── pipelines/
│   ├── training/
│   └── evaluation/
├── docs/
│   ├── api.md
│   ├── simulator.md
│   └── security.md
├── README.md
├── ARCHITECTURE.md
├── .gitignore
├── .env.example
└── package-lock.json (if monorepo tooling is used)
```

## 13. Implementation Plan

### Phase 1: foundation and architecture
- define schemas and failure taxonomy
- create project skeleton
- set up repo structure
- define deployment constraints
- create architecture and readme docs

### Phase 2: synthetic data and ingestion
- generate synthetic payment and checkout data
- create event ingestion pipeline
- validate event normalization and deduplication

### Phase 3: risk and recoverability ML
- label synthetic data for recoverability and outcomes
- train baseline models
- evaluate model metrics
- save model artifacts

### Phase 4: policy and simulator engine
- define deterministic action rules
- implement payment simulator
- enforce safety checks and audit logging

### Phase 5: agent orchestration
- integrate LangGraph workflow
- add LLM provider abstraction
- implement fallback reasoning path
- ensure policy enforcement layer remains authoritative

### Phase 6: dashboard and evaluation
- build revenue dashboard with Recharts
- compare baseline vs AI decisions
- measure recovery amount and success rates
- add audit and evaluation views

### Phase 7: hardening and demo polish
- error handling and schema validation
- security controls and traceability
- final performance checks
- launch-ready documentation

## 14. Recommended Approach for Hackathon Delivery

- Keep the core business logic deterministic and explainable.
- Use synthetic but realistic scenarios to show impact clearly.
- Prioritize a clean demo flow: detect, explain, decide, simulate, measure.
- Make the LLM enhancement visible but never dominant over policy enforcement.
- Show recovery value in a simple dashboard with baseline comparison.

## 15. Future Replaceability

The design intentionally isolates the payment execution component behind an interface. A real provider such as Razorpay, Stripe, or another internal gateway could be wired in later without rewriting the decision engine, simulator, or dashboard stack.

The current implementation is simulation-only and should be documented as such in all user-facing outputs.
