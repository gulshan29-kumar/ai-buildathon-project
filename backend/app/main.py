from __future__ import annotations

from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.decision_engine import DecisionEngine
from backend.app.failure_classifier import FailureClassifier
from backend.app.policy_engine import PolicyEngine
from backend.app.simulator import PaymentSimulator, PolicyBlockedExecutionError

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

decision_engine = DecisionEngine()
simulator = PaymentSimulator()
policy_engine = PolicyEngine()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "razorrecover-ai-backend"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "project": settings.APP_NAME,
        "tagline": "Autonomous Revenue Recovery for Failed Payments and Abandoned Checkouts",
        "mode": "simulation-only",
    }


@app.post("/api/classify")
def classify_failure(payload: Dict[str, Any]) -> Dict[str, Any]:
    code = payload.get("failure_code", "")
    res = FailureClassifier.classify(code)
    return res.to_dict()


@app.post("/api/decide")
def evaluate_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    decision = decision_engine.decide(
        transaction=payload.get("transaction"),
        customer_context=payload.get("customer_context"),
        payment_context=payload.get("payment_context"),
        action_probabilities=payload.get("action_probabilities"),
        available_payment_methods=payload.get("available_payment_methods"),
    )
    return decision.to_dict()


@app.post("/api/simulate/retry")
def simulate_retry(payload: Dict[str, Any]) -> Dict[str, Any]:
    txn_id = payload.get("transaction_id", "")
    delay = payload.get("delay_seconds", 0)
    try:
        res = simulator.retry_payment(txn_id, delay_seconds=delay)
        return res
    except PolicyBlockedExecutionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/simulate/switch")
def simulate_switch(payload: Dict[str, Any]) -> Dict[str, Any]:
    txn_id = payload.get("transaction_id", "")
    method = payload.get("new_payment_method", "UPI")
    try:
        res = simulator.switch_payment_method(txn_id, new_payment_method=method)
        return res
    except PolicyBlockedExecutionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/simulate/message")
def simulate_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    txn_id = payload.get("transaction_id", "")
    channel = payload.get("channel", "WHATSAPP")
    try:
        res = simulator.send_recovery_message(txn_id, channel=channel)
        return res
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/simulator/status/{transaction_id}")
def get_sim_status(transaction_id: str) -> Dict[str, Any]:
    try:
        return simulator.get_payment_status(transaction_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/policies")
def list_policies() -> Dict[str, Any]:
    return {
        "policies": [
            {"rule_id": "POL-001", "name": "Never Retry Success", "outcome": "DENY", "severity": "CRITICAL"},
            {"rule_id": "POL-002", "name": "Never Retry Duplicate", "outcome": "DENY", "severity": "CRITICAL"},
            {"rule_id": "POL-003", "name": "Block High-Risk Auto-Recovery", "outcome": "ESCALATE", "severity": "CRITICAL"},
            {"rule_id": "POL-004", "name": "Enforce Retry Limits", "outcome": "DENY", "severity": "HIGH"},
            {"rule_id": "POL-005", "name": "Enforce Retry Cooldown", "outcome": "WAIT", "severity": "MEDIUM"},
            {"rule_id": "POL-006", "name": "Escalate High-Value Risky", "outcome": "ESCALATE", "severity": "HIGH"},
            {"rule_id": "POL-007", "name": "Wait on Pending Payments", "outcome": "WAIT", "severity": "HIGH"},
            {"rule_id": "POL-008", "name": "Stop on Invalid State", "outcome": "DENY", "severity": "CRITICAL"},
            {"rule_id": "POL-009", "name": "Respect Customer DND / Opt-Out", "outcome": "DENY", "severity": "MEDIUM"},
            {"rule_id": "POL-010", "name": "Audit Every Denial", "outcome": "AUDIT", "severity": "HIGH"},
            {"rule_id": "POL-011", "name": "LLM Cannot Bypass Policy", "outcome": "DENY", "severity": "CRITICAL"},
            {"rule_id": "POL-012", "name": "Policy Runs Before Execution", "outcome": "ENFORCE", "severity": "CRITICAL"},
        ]
    }

