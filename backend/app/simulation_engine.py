from __future__ import annotations

import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.action_predictor import ActionRecoveryPredictor
from backend.app.audit_trail import AuditTrail
from backend.app.decision_engine import DecisionEngine
from backend.app.failure_classifier import FailureClassifier
from backend.app.ml.inference import (
    predict_batch_recovery_probabilities,
    predict_recovery_probability,
)
from backend.app.policy_engine import PolicyEngine, PolicyOutcome
from backend.app.simulator import PaymentSimulator, PaymentState, PolicyBlockedExecutionError

logger = logging.getLogger(__name__)

SIMULATIONS_DIR = Path("backend/data/simulations")
SIMULATIONS_DIR.mkdir(parents=True, exist_ok=True)


class SimulationEngine:
    """Engine for large-scale comparative revenue recovery simulations.
    
    Compares:
      1. BASELINE: Simple non-intelligent naive recovery strategy (blind 1-time retry on same rail).
      2. RAZORRECOVER AI: Complete intelligent autonomous pipeline:
         Synthetic Events → ML → Root Cause → Action Ranking → Policy Guardrails → Simulator → Result → Audit.
    """

    def __init__(self, seed: Optional[int] = 42):
        self.seed = seed or 42
        self.rng = random.Random(self.seed)
        self.classifier = FailureClassifier()
        self.action_predictor = ActionRecoveryPredictor()
        self.policy_engine = PolicyEngine()
        self.decision_engine = DecisionEngine(policy_engine=self.policy_engine)
        self.simulator = PaymentSimulator(seed=self.seed, policy_engine=self.policy_engine)
        self.audit_trail = AuditTrail.get_instance()

    def generate_synthetic_transactions(
        self, count: int, scenario: str = "mixed_failures"
    ) -> List[Dict[str, Any]]:
        """Generates realistic synthetic payment events with detailed customer & payment context."""
        rng = self.rng

        failure_code_pool: List[Tuple[str, float]]
        if scenario == "gateway_outage":
            failure_code_pool = [
                ("GATEWAY_TIMEOUT", 0.50),
                ("BANK_UNAVAILABLE", 0.35),
                ("CARD_DECLINED", 0.05),
                ("CUSTOMER_ABANDONED", 0.05),
                ("HIGH_RISK", 0.05),
            ]
        elif scenario == "abandonment_surge":
            failure_code_pool = [
                ("CUSTOMER_ABANDONED", 0.55),
                ("OTP_EXPIRED", 0.20),
                ("GATEWAY_TIMEOUT", 0.10),
                ("CARD_DECLINED", 0.10),
                ("HIGH_RISK", 0.05),
            ]
        elif scenario == "high_risk_influx":
            failure_code_pool = [
                ("HIGH_RISK", 0.40),
                ("CARD_DECLINED", 0.25),
                ("GATEWAY_TIMEOUT", 0.15),
                ("CUSTOMER_ABANDONED", 0.10),
                ("BANK_UNAVAILABLE", 0.10),
            ]
        else:  # mixed_failures
            failure_code_pool = [
                ("GATEWAY_TIMEOUT", 0.25),
                ("CARD_DECLINED", 0.22),
                ("BANK_UNAVAILABLE", 0.18),
                ("CUSTOMER_ABANDONED", 0.15),
                ("OTP_EXPIRED", 0.10),
                ("HIGH_RISK", 0.10),
            ]

        codes, weights = zip(*failure_code_pool)

        synthetic_events = []
        customer_first_names = [
            "Aarav", "Aditi", "Priya", "Rahul", "Ananya", "Rohan", "Sneha", "Vikram",
            "Deepa", "Karan", "Pooja", "Arjun", "Meera", "Siddharth", "Ishita", "Sanjay",
        ]

        for i in range(count):
            t_id = f"txn_sim_{uuid.uuid4().hex[:8]}"
            f_code = rng.choices(codes, weights=weights, k=1)[0]
            is_risk = f_code == "HIGH_RISK"

            method = rng.choices(
                ["UPI", "CARD", "NETBANKING", "WALLET"],
                weights=[0.55, 0.30, 0.12, 0.03],
                k=1,
            )[0]

            if method == "CARD":
                amt = round(rng.uniform(800.0, 38000.0), 2)
            elif method == "NETBANKING":
                amt = round(rng.uniform(1500.0, 48000.0), 2)
            else:
                amt = round(rng.uniform(150.0, 12500.0), 2)

            if is_risk:
                risk_score = round(rng.uniform(0.86, 0.98), 2)
                success_rate = round(rng.uniform(0.15, 0.45), 2)
                historical_declines = rng.randint(3, 8)
                total_orders = rng.randint(1, 6)
            else:
                risk_score = round(rng.uniform(0.01, 0.25), 2)
                success_rate = round(rng.uniform(0.80, 0.98), 2)
                historical_declines = rng.randint(0, 2)
                total_orders = rng.randint(5, 45)

            cust_name = rng.choice(customer_first_names).lower()
            cust_id = f"cust_{cust_name}_{rng.randint(10, 99)}"

            recoverable = not is_risk

            event = {
                "transaction_id": t_id,
                "amount": amt,
                "currency": "INR",
                "payment_method": method,
                "failure_code": f_code,
                "risk_score": risk_score,
                "customer_id": cust_id,
                "attempt_number": 1,
                "recoverable": recoverable,
                "customer_history": {
                    "total_orders": total_orders,
                    "success_rate": success_rate,
                    "historical_declines": historical_declines,
                    "risk_tier": "CRITICAL_RISK" if is_risk else "LOW",
                    "average_transaction": round(amt * rng.uniform(0.8, 1.2), 2),
                },
                "payment_context": {
                    "gateway": "RAZORPAY_SIMULATED",
                    "flow_stage": "FRAUD_CHECK" if is_risk else "AUTHORIZATION",
                    "retry_eligible": not is_risk,
                    "idempotency_key": f"idemp_{t_id}",
                    "checkout_duration": round(rng.uniform(15.0, 120.0), 1),
                    "device_type": rng.choice(["MOBILE", "DESKTOP"]),
                },
            }
            synthetic_events.append(event)

        return synthetic_events

    def run_baseline_strategy(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a simple non-intelligent baseline recovery strategy."""
        f_code = event["failure_code"]
        amount = event["amount"]
        risk_score = event["risk_score"]

        retry_attempted = True
        blocked = False
        escalated = False
        recovered = False
        execution_status = "FAILED"
        recovery_time_ms = 750.0

        is_unnecessary = False

        if risk_score > 0.85 or f_code == "HIGH_RISK":
            is_unnecessary = True
            recovered = False
            execution_status = "BLOCKED_BY_ACQUIRER"
            recovery_time_ms = 400.0
        elif f_code in ("GATEWAY_TIMEOUT", "BANK_UNAVAILABLE"):
            success_prob = 0.35 if f_code == "GATEWAY_TIMEOUT" else 0.28
            recovered = self.rng.random() < success_prob
            execution_status = "SUCCESS" if recovered else "FAILED"
            recovery_time_ms = 850.0
        elif f_code in ("CARD_DECLINED", "CARD_EXPIRED"):
            is_unnecessary = True
            recovered = False
            execution_status = "DECLINED_AGAIN"
            recovery_time_ms = 700.0
        elif f_code == "CUSTOMER_ABANDONED":
            is_unnecessary = True
            recovered = False
            execution_status = "SESSION_EXPIRED"
            recovery_time_ms = 500.0
        elif f_code == "OTP_EXPIRED":
            is_unnecessary = True
            recovered = False
            execution_status = "OTP_INVALID"
            recovery_time_ms = 600.0
        else:
            recovered = False
            execution_status = "FAILED"

        return {
            "strategy": "BASELINE",
            "selected_action": "RETRY_PAYMENT",
            "action_type": "BLIND_RETRY",
            "execution_status": execution_status,
            "recovered": recovered,
            "recovered_amount": amount if recovered else 0.0,
            "recovery_time_ms": recovery_time_ms,
            "retry_attempts": 1,
            "blocked": blocked,
            "escalated": escalated,
            "unnecessary_intervention": is_unnecessary,
        }

    def run_ai_strategy(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the full RazorRecover AI intelligent pipeline."""
        amount = event["amount"]
        f_code = event["failure_code"]
        risk_score = event["risk_score"]
        t_id = event["transaction_id"]

        # 1. Root Cause Classification
        root_cause_res = self.classifier.classify(f_code)
        category = root_cause_res.category.value if hasattr(root_cause_res, "category") else "UNKNOWN"

        # 2. ML Recoverability Prediction
        recovery_prob = event.get("predicted_recovery_prob")
        if recovery_prob is None:
            ml_res = predict_recovery_probability(event)
            recovery_prob = ml_res.get("probability", 0.5)

        # 3. Action Candidate Ranking
        candidates = sorted(
            self.action_predictor.evaluate_all(event),
            key=lambda c: c.get("expected_recovery_value", 0.0),
            reverse=True,
        )

        # 4. Policy Guardrail Evaluation
        best_permitted_action = "STOP"
        policy_decision_record = None

        for cand in candidates:
            p_decision = self.policy_engine.evaluate(
                event={**event, "action": cand["action"]},
                customer_risk=risk_score,
                previous_attempts=event.get("attempt_number", 1) - 1,
            )
            cand["policy_outcome"] = "ALLOWED" if p_decision.allowed else "DENIED"
            cand["rule_id"] = p_decision.rule_id
            cand["reason"] = p_decision.reason

            if p_decision.allowed and cand.get("expected_recovery_value", 0.0) > 0:
                best_permitted_action = cand["action"]
                policy_decision_record = p_decision
                break
            elif not p_decision.allowed and risk_score > 0.85:
                best_permitted_action = "ESCALATE"
                policy_decision_record = p_decision
                break

        if best_permitted_action == "STOP":
            if risk_score > 0.85 or f_code == "HIGH_RISK":
                best_permitted_action = "ESCALATE"
            elif category == "TEMPORARY":
                best_permitted_action = "RETRY_PAYMENT"
            elif category == "PAYMENT_METHOD":
                best_permitted_action = "SWITCH_PAYMENT_METHOD"
            elif category == "ABANDONMENT":
                best_permitted_action = "SEND_RECOVERY_LINK"

        # 5. Simulator Execution
        recovered = False
        execution_status = "PENDING"
        blocked = False
        escalated = False
        retry_attempts = 0
        unnecessary = False
        recovery_time_ms = 1200.0

        if best_permitted_action == "ESCALATE":
            escalated = True
            blocked = True
            execution_status = "BLOCKED_BY_POLICY"
            recovered = False
            recovery_time_ms = 350.0
        elif best_permitted_action == "RETRY_PAYMENT":
            retry_attempts = 1
            success_prob = 0.86 if category == "TEMPORARY" else 0.40
            recovered = self.rng.random() < success_prob
            execution_status = "SUCCESS" if recovered else "FAILED"
            recovery_time_ms = 1650.0
        elif best_permitted_action == "SWITCH_PAYMENT_METHOD":
            recovered = self.rng.random() < 0.84
            execution_status = "SUCCESS" if recovered else "FAILED"
            recovery_time_ms = 2200.0
        elif best_permitted_action == "SEND_RECOVERY_LINK":
            recovered = self.rng.random() < 0.72
            execution_status = "SUCCESS" if recovered else "NO_CUSTOMER_RESPONSE"
            recovery_time_ms = 3100.0
        else:
            recovered = False
            execution_status = "STOPPED"
            recovery_time_ms = 500.0

        if best_permitted_action in ("RETRY_PAYMENT", "SWITCH_PAYMENT_METHOD") and risk_score > 0.85:
            unnecessary = True

        # 6. Audit Trail Logging (SHA-256 chained)
        audit_event = self.audit_trail.log_event(
            transaction_id=t_id,
            event_type="SIMULATION_RECOVERY_RUN",
            actor="ORCHESTRATOR",
            selected_action=best_permitted_action,
            revenue_recovered=amount if recovered else 0.0,
            execution_result={"status": execution_status, "strategy": "AI"},
            policy_result="ALLOWED" if (policy_decision_record and policy_decision_record.allowed) else "DENIED",
            policy_rule=policy_decision_record.rule_id if policy_decision_record else "POL-005",
        )

        return {
            "strategy": "RAZORRECOVER_AI",
            "selected_action": best_permitted_action,
            "root_cause_category": category,
            "ml_recovery_probability": round(recovery_prob, 4),
            "policy_outcome": "ALLOWED" if (policy_decision_record and policy_decision_record.allowed) else "DENIED",
            "policy_rule_id": policy_decision_record.rule_id if policy_decision_record else "POL-005",
            "execution_status": execution_status,
            "recovered": recovered,
            "recovered_amount": amount if recovered else 0.0,
            "recovery_time_ms": recovery_time_ms,
            "retry_attempts": retry_attempts,
            "blocked": blocked,
            "escalated": escalated,
            "unnecessary_intervention": unnecessary,
            "audit_hash": getattr(audit_event, "hash", "") if audit_event else "",
        }

    def run_comparison(
        self,
        transaction_count: int = 50,
        seed: Optional[int] = None,
        scenario: str = "mixed_failures",
    ) -> Dict[str, Any]:
        """Runs batch simulation comparing BASELINE vs RAZORRECOVER AI across all 11 metrics."""
        if seed is not None:
            self.seed = seed
            self.rng = random.Random(seed)
            self.simulator = PaymentSimulator(seed=seed, policy_engine=self.policy_engine)

        run_id = f"sim_run_{uuid.uuid4().hex[:10]}"
        created_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Generate Synthetic Events
        synthetic_events = self.generate_synthetic_transactions(
            count=transaction_count, scenario=scenario
        )

        # Vectorized batch inference for instant ML scoring
        batch_probs = predict_batch_recovery_probabilities(synthetic_events)
        for idx, ev in enumerate(synthetic_events):
            ev["predicted_recovery_prob"] = batch_probs[idx]

        # Baseline accumulators
        base_recovered_count = 0
        base_recovered_revenue = 0.0
        base_retry_attempts = 0
        base_blocked_actions = 0
        base_escalations = 0
        base_unnecessary_interventions = 0
        base_total_time_ms = 0.0

        # AI accumulators
        ai_recovered_count = 0
        ai_recovered_revenue = 0.0
        ai_retry_attempts = 0
        ai_blocked_actions = 0
        ai_escalations = 0
        ai_unnecessary_interventions = 0
        ai_total_time_ms = 0.0

        total_transactions = len(synthetic_events)
        failed_transactions = total_transactions
        recoverable_opportunities = sum(1 for e in synthetic_events if e.get("recoverable", True))
        revenue_at_risk = round(sum(e["amount"] for e in synthetic_events), 2)

        comparison_traces = []
        category_breakdown: Dict[str, Dict[str, Any]] = {}
        ai_actions_distribution: Dict[str, int] = {}

        for event in synthetic_events:
            f_code = event["failure_code"]
            if f_code not in category_breakdown:
                category_breakdown[f_code] = {
                    "total": 0,
                    "baseline_recovered": 0,
                    "ai_recovered": 0,
                    "revenue_at_risk": 0.0,
                    "ai_recovered_revenue": 0.0,
                }
            category_breakdown[f_code]["total"] += 1
            category_breakdown[f_code]["revenue_at_risk"] += event["amount"]

            # Run Baseline Strategy
            base_res = self.run_baseline_strategy(event)
            if base_res["recovered"]:
                base_recovered_count += 1
                base_recovered_revenue += base_res["recovered_amount"]
                category_breakdown[f_code]["baseline_recovered"] += 1
            base_retry_attempts += base_res["retry_attempts"]
            if base_res["blocked"]:
                base_blocked_actions += 1
            if base_res["escalated"]:
                base_escalations += 1
            if base_res["unnecessary_intervention"]:
                base_unnecessary_interventions += 1
            base_total_time_ms += base_res["recovery_time_ms"]

            # Run AI Strategy
            ai_res = self.run_ai_strategy(event)
            if ai_res["recovered"]:
                ai_recovered_count += 1
                ai_recovered_revenue += ai_res["recovered_amount"]
                category_breakdown[f_code]["ai_recovered"] += 1
                category_breakdown[f_code]["ai_recovered_revenue"] += ai_res["recovered_amount"]
            ai_retry_attempts += ai_res["retry_attempts"]
            if ai_res["blocked"]:
                ai_blocked_actions += 1
            if ai_res["escalated"]:
                ai_escalations += 1
            if ai_res["unnecessary_intervention"]:
                ai_unnecessary_interventions += 1
            ai_total_time_ms += ai_res["recovery_time_ms"]

            act = ai_res["selected_action"]
            ai_actions_distribution[act] = ai_actions_distribution.get(act, 0) + 1

            # Individual Transaction Trace for Granular Inspection
            trace = {
                "transaction_id": event["transaction_id"],
                "amount": event["amount"],
                "currency": event["currency"],
                "payment_method": event["payment_method"],
                "failure_code": event["failure_code"],
                "risk_score": event["risk_score"],
                "customer_id": event["customer_id"],
                "customer_history": event["customer_history"],
                "payment_context": event["payment_context"],
                "recoverable": event["recoverable"],
                "baseline": {
                    "action": base_res["selected_action"],
                    "status": base_res["execution_status"],
                    "recovered": base_res["recovered"],
                    "recovered_amount": base_res["recovered_amount"],
                    "time_ms": base_res["recovery_time_ms"],
                    "unnecessary": base_res["unnecessary_intervention"],
                },
                "ai": {
                    "action": ai_res["selected_action"],
                    "root_cause": ai_res["root_cause_category"],
                    "recovery_probability": ai_res["ml_recovery_probability"],
                    "policy_decision": ai_res["policy_outcome"],
                    "policy_rule_id": ai_res["policy_rule_id"],
                    "status": ai_res["execution_status"],
                    "recovered": ai_res["recovered"],
                    "recovered_amount": ai_res["recovered_amount"],
                    "time_ms": ai_res["recovery_time_ms"],
                    "blocked": ai_res["blocked"],
                    "escalated": ai_res["escalated"],
                    "unnecessary": ai_res["unnecessary_intervention"],
                    "audit_hash": ai_res["audit_hash"],
                },
                "ai_won": ai_res["recovered"] and not base_res["recovered"],
            }
            comparison_traces.append(trace)

        base_recovery_rate = round(base_recovered_count / failed_transactions, 4) if failed_transactions > 0 else 0.0
        ai_recovery_rate = round(ai_recovered_count / failed_transactions, 4) if failed_transactions > 0 else 0.0

        base_avg_time_ms = round(base_total_time_ms / total_transactions, 1) if total_transactions > 0 else 0.0
        ai_avg_time_ms = round(ai_total_time_ms / total_transactions, 1) if total_transactions > 0 else 0.0

        base_intervention_rate = (
            round(base_unnecessary_interventions / base_retry_attempts, 4)
            if base_retry_attempts > 0
            else 0.0
        )
        ai_total_interventions = ai_retry_attempts + (total_transactions - ai_escalations)
        ai_intervention_rate = (
            round(ai_unnecessary_interventions / max(ai_total_interventions, 1), 4)
        )

        revenue_gain = round(ai_recovered_revenue - base_recovered_revenue, 2)
        revenue_uplift_pct = (
            round((revenue_gain / base_recovered_revenue) * 100, 2)
            if base_recovered_revenue > 0
            else 100.0
        )
        recovery_rate_diff = round((ai_recovery_rate - base_recovery_rate) * 100, 2)

        result = {
            "run_id": run_id,
            "seed": self.seed,
            "created_at": created_at,
            "scenario": scenario,
            "total_transactions": total_transactions,
            "failed_transactions": failed_transactions,
            "recoverable_opportunities": recoverable_opportunities,
            "revenue_at_risk": revenue_at_risk,
            "baseline_metrics": {
                "total_transactions": total_transactions,
                "failed_transactions": failed_transactions,
                "recoverable_opportunities": recoverable_opportunities,
                "revenue_at_risk": revenue_at_risk,
                "recovered_revenue": round(base_recovered_revenue, 2),
                "recovered_count": base_recovered_count,
                "recovery_rate": base_recovery_rate,
                "average_recovery_time_ms": base_avg_time_ms,
                "retry_attempts": base_retry_attempts,
                "blocked_actions": base_blocked_actions,
                "escalations": base_escalations,
                "unnecessary_intervention_rate": base_intervention_rate,
            },
            "ai_metrics": {
                "total_transactions": total_transactions,
                "failed_transactions": failed_transactions,
                "recoverable_opportunities": recoverable_opportunities,
                "revenue_at_risk": revenue_at_risk,
                "recovered_revenue": round(ai_recovered_revenue, 2),
                "recovered_count": ai_recovered_count,
                "recovery_rate": ai_recovery_rate,
                "average_recovery_time_ms": ai_avg_time_ms,
                "retry_attempts": ai_retry_attempts,
                "blocked_actions": ai_blocked_actions,
                "escalations": ai_escalations,
                "unnecessary_intervention_rate": ai_intervention_rate,
            },
            "uplift": {
                "revenue_gain": revenue_gain,
                "revenue_uplift_pct": revenue_uplift_pct,
                "recovery_rate_diff_pct": recovery_rate_diff,
                "intervention_reduction_pct": round(
                    max(0.0, (base_intervention_rate - ai_intervention_rate) * 100), 2
                ),
            },
            "category_breakdown": category_breakdown,
            "ai_actions_distribution": ai_actions_distribution,
            "transactions": comparison_traces,
            "status": "COMPLETED",
        }

        self._persist_run(run_id, result)

        logger.info(
            f"Simulation {run_id} completed: Baseline={base_recovery_rate*100:.1f}%, AI={ai_recovery_rate*100:.1f}%, Revenue Gain=+₹{revenue_gain:,.2f}"
        )
        return result

    def _persist_run(self, run_id: str, data: Dict[str, Any]) -> None:
        """Persists full simulation comparison results to disk in JSON format."""
        try:
            file_path = SIMULATIONS_DIR / f"{run_id}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist simulation {run_id} to disk: {e}")

    @staticmethod
    def load_run(run_id: str) -> Optional[Dict[str, Any]]:
        """Loads a persisted simulation run from disk."""
        file_path = SIMULATIONS_DIR / f"{run_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read simulation file {file_path}: {e}")
            return None

    @staticmethod
    def list_runs(limit: int = 20) -> List[Dict[str, Any]]:
        """Lists metadata for all saved simulation runs."""
        runs = []
        if not SIMULATIONS_DIR.exists():
            return []

        for p in sorted(SIMULATIONS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)[:limit]:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    runs.append({
                        "run_id": d.get("run_id"),
                        "seed": d.get("seed"),
                        "created_at": d.get("created_at"),
                        "scenario": d.get("scenario"),
                        "total_transactions": d.get("total_transactions"),
                        "revenue_at_risk": d.get("revenue_at_risk"),
                        "baseline_recovered_revenue": d.get("baseline_metrics", {}).get("recovered_revenue"),
                        "ai_recovered_revenue": d.get("ai_metrics", {}).get("recovered_revenue"),
                        "baseline_recovery_rate": d.get("baseline_metrics", {}).get("recovery_rate"),
                        "ai_recovery_rate": d.get("ai_metrics", {}).get("recovery_rate"),
                        "revenue_gain": d.get("uplift", {}).get("revenue_gain"),
                    })
            except Exception:
                continue

        return runs
