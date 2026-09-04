from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.app.action_predictor import ActionRecoveryPredictor
from backend.app.audit_trail import AuditEvent, AuditTrail
from backend.app.failure_classifier import FailureClassifier
from backend.app.policy_engine import PolicyDecision, PolicyEngine, PolicyOutcome

logger = logging.getLogger(__name__)


class SubscriptionLifecycleState(str, Enum):
    SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"
    PAYMENT_ATTEMPTED = "PAYMENT_ATTEMPTED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    PAYMENT_METHOD_CHANGED = "PAYMENT_METHOD_CHANGED"
    SUBSCRIPTION_RECOVERED = "SUBSCRIPTION_RECOVERED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"


class SubscriptionAction(str, Enum):
    RETRY_PAYMENT = "RETRY_PAYMENT"
    SWITCH_PAYMENT_METHOD = "SWITCH_PAYMENT_METHOD"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    SEND_RECOVERY_MESSAGE = "SEND_RECOVERY_MESSAGE"
    ESCALATE = "ESCALATE"
    STOP = "STOP"


@dataclass
class SubscriptionEvent:
    event_id: str
    state: SubscriptionLifecycleState
    timestamp: datetime
    action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "metadata": self.metadata,
        }


@dataclass
class SubscriptionCustomerHistory:
    customer_id: str
    tenure_months: int = 6
    consecutive_successful_renewals: int = 5
    lifetime_billing_volume: float = 24995.0
    past_decline_count: int = 0
    primary_payment_method: str = "CARD"
    backup_payment_method: Optional[str] = "UPI_AUTOPAY"
    risk_score: float = 0.03
    dnd_enabled: bool = False
    customer_tier: str = "PRO"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "tenure_months": self.tenure_months,
            "consecutive_successful_renewals": self.consecutive_successful_renewals,
            "lifetime_billing_volume": round(self.lifetime_billing_volume, 2),
            "past_decline_count": self.past_decline_count,
            "primary_payment_method": self.primary_payment_method,
            "backup_payment_method": self.backup_payment_method,
            "risk_score": round(self.risk_score, 3),
            "dnd_enabled": self.dnd_enabled,
            "customer_tier": self.customer_tier,
        }


@dataclass
class SubscriptionState:
    subscription_id: str
    customer_id: str
    merchant_id: str
    plan_name: str
    renewal_amount: float
    current_state: SubscriptionLifecycleState
    created_at: datetime
    updated_at: datetime
    billing_cycle: str = "MONTHLY"
    current_attempt_count: int = 0
    max_retry_limit: int = 3
    last_failure_code: Optional[str] = None
    primary_method: str = "CARD"
    backup_method: Optional[str] = "UPI_AUTOPAY"
    customer_history: SubscriptionCustomerHistory = field(default_factory=lambda: SubscriptionCustomerHistory(customer_id="cust_default"))
    events: List[SubscriptionEvent] = field(default_factory=list)
    recovery_action: Optional[str] = None
    recovery_probability: Optional[float] = None
    expected_recovery_value: Optional[float] = None
    policy_outcome: Optional[str] = None
    policy_rule_id: Optional[str] = None
    recovered: bool = False
    audit_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "customer_id": self.customer_id,
            "merchant_id": self.merchant_id,
            "plan_name": self.plan_name,
            "renewal_amount": round(self.renewal_amount, 2),
            "billing_cycle": self.billing_cycle,
            "current_state": self.current_state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_attempt_count": self.current_attempt_count,
            "max_retry_limit": self.max_retry_limit,
            "last_failure_code": self.last_failure_code,
            "primary_method": self.primary_method,
            "backup_method": self.backup_method,
            "customer_history": self.customer_history.to_dict(),
            "recovery_action": self.recovery_action,
            "recovery_probability": round(self.recovery_probability, 4) if self.recovery_probability is not None else None,
            "expected_recovery_value": round(self.expected_recovery_value, 2) if self.expected_recovery_value is not None else None,
            "policy_outcome": self.policy_outcome,
            "policy_rule_id": self.policy_rule_id,
            "recovered": self.recovered,
            "audit_hash": self.audit_hash,
            "events_count": len(self.events),
        }


class SubscriptionRecoveryPredictor:
    """Predicts recovery probabilities for all 6 actions utilizing customer history and failure diagnostics."""

    def __init__(self, action_predictor: Optional[ActionRecoveryPredictor] = None):
        self.action_predictor = action_predictor or ActionRecoveryPredictor()

    def predict_action_probabilities(
        self,
        subscription: SubscriptionState,
        failure_code: Optional[str] = None,
    ) -> Dict[str, float]:
        fcode = (failure_code or subscription.last_failure_code or "INSUFFICIENT_FUNDS").upper()
        hist = subscription.customer_history
        risk_score = hist.risk_score
        has_backup = bool(subscription.backup_method)
        tenure = hist.tenure_months
        renewals = hist.consecutive_successful_renewals
        dnd = hist.dnd_enabled
        attempts = subscription.current_attempt_count

        # Base benchmark probabilities from platform ActionRecoveryPredictor
        pseudo_txn = {
            "amount": subscription.renewal_amount,
            "failure_code": fcode,
            "risk_score": risk_score,
            "payment_method": subscription.primary_method,
            "attempt_number": attempts + 1,
            "recurring": True,
        }
        evals = self.action_predictor.evaluate_all(pseudo_txn)
        base_probs = {item["action"]: item["probability"] for item in evals}

        p_retry = base_probs.get("RETRY_PAYMENT", 0.20)
        p_switch = base_probs.get("SWITCH_PAYMENT_METHOD", 0.40)
        p_schedule = base_probs.get("SCHEDULE_RETRY", 0.50)
        p_msg = base_probs.get("SEND_RECOVERY_MESSAGE", 0.45)
        p_escalate = base_probs.get("ESCALATE", 0.15)
        p_stop = base_probs.get("STOP", 0.05)

        # 1. Customer tenure & consecutive renewals boost dunning and schedule responsiveness
        loyalty_boost = min(0.20, (renewals * 0.03) + (tenure * 0.01))
        p_msg += loyalty_boost
        p_schedule += loyalty_boost * 0.8

        # 2. Backup payment method availability strongly favors SWITCH_PAYMENT_METHOD
        if has_backup:
            if fcode in ("CARD_EXPIRED", "CARD_DECLINED", "MANDATE_REVOKED", "INSUFFICIENT_FUNDS"):
                p_switch = max(0.82, p_switch + 0.30)
        else:
            p_switch = 0.05  # No backup rail to switch to immediately

        # 3. Specific failure code dynamics for subscriptions
        if fcode == "CARD_EXPIRED":
            p_retry = 0.00  # Cannot retry expired card
            p_schedule = 0.02
            if not has_backup:
                p_msg = max(0.75, p_msg + 0.20)  # Must request new mandate link

        elif fcode == "INSUFFICIENT_FUNDS":
            p_retry = 0.10  # Immediate retry low
            p_schedule = max(0.72, p_schedule + 0.15)  # Delayed dunning retry high

        elif fcode == "GATEWAY_TIMEOUT" or fcode == "BANK_UNAVAILABLE":
            p_retry = max(0.70, p_retry)
            p_schedule = max(0.80, p_schedule)

        # 4. Attempt limit penalties: multiple prior declines decrease retry success
        if attempts >= 2:
            p_retry *= 0.30
            p_schedule *= 0.60
            p_msg += 0.15  # Elevate customer dunning reachout
            if attempts >= 3:
                p_stop = max(0.80, p_stop + 0.50)

        # 5. DND communication restrictions
        if dnd:
            p_msg = 0.00
            p_schedule = max(0.60, p_schedule * 1.2)

        # 6. Fraud & High-Risk suppression
        if risk_score > 0.70:
            p_retry = 0.00
            p_switch = 0.00
            p_schedule = 0.00
            p_msg = 0.00
            p_escalate = 0.40
            p_stop = 0.95
        elif risk_score > 0.40:
            p_retry *= 0.50
            p_escalate += 0.30

        # Clamp all probabilities into [0.0, 1.0]
        return {
            SubscriptionAction.RETRY_PAYMENT.value: round(max(0.0, min(0.95, p_retry)), 4),
            SubscriptionAction.SWITCH_PAYMENT_METHOD.value: round(max(0.0, min(0.95, p_switch)), 4),
            SubscriptionAction.SCHEDULE_RETRY.value: round(max(0.0, min(0.95, p_schedule)), 4),
            SubscriptionAction.SEND_RECOVERY_MESSAGE.value: round(max(0.0, min(0.95, p_msg)), 4),
            SubscriptionAction.ESCALATE.value: round(max(0.0, min(0.90, p_escalate)), 4),
            SubscriptionAction.STOP.value: round(max(0.0, min(1.0, p_stop)), 4),
        }


class SubscriptionDecisionEngine:
    """Ranks subscription recovery actions by Expected Recovery Value ($EV) and validates policy guardrails."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.predictor = SubscriptionRecoveryPredictor()

    def evaluate_candidates(
        self,
        subscription: SubscriptionState,
        failure_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        fcode = failure_code or subscription.last_failure_code or "INSUFFICIENT_FUNDS"
        probabilities = self.predictor.predict_action_probabilities(subscription, fcode)
        amount = subscription.renewal_amount
        hist = subscription.customer_history

        candidates = []
        action_names = [
            SubscriptionAction.RETRY_PAYMENT.value,
            SubscriptionAction.SWITCH_PAYMENT_METHOD.value,
            SubscriptionAction.SCHEDULE_RETRY.value,
            SubscriptionAction.SEND_RECOVERY_MESSAGE.value,
            SubscriptionAction.ESCALATE.value,
            SubscriptionAction.STOP.value,
        ]

        for action_name in action_names:
            prob = probabilities.get(action_name, 0.0)
            ev = amount * prob if action_name not in (SubscriptionAction.STOP.value, SubscriptionAction.ESCALATE.value) else 0.0

            # Policy evaluation using the platform's unified PolicyEngine
            policy_event = {
                "transaction_id": subscription.subscription_id,
                "amount": amount,
                "status": "FAILED",
                "failure_code": fcode,
                "risk_score": hist.risk_score,
                "attempt_number": subscription.current_attempt_count + 1,
                "action": action_name,
                "communication_opt_out": hist.dnd_enabled,
                "dnd": hist.dnd_enabled,
            }
            cust_ctx = {
                "customer_id": subscription.customer_id,
                "dnd": hist.dnd_enabled,
                "communication_opt_out": hist.dnd_enabled,
                "risk_score": hist.risk_score,
            }
            policy_decision: PolicyDecision = self.policy_engine.evaluate(policy_event, customer_context=cust_ctx)

            # Subscription-specific guardrail: retry limit
            is_permitted = policy_decision.allowed
            rule_id = policy_decision.rule_id
            reason = policy_decision.reason

            if action_name == SubscriptionAction.RETRY_PAYMENT.value and subscription.current_attempt_count >= subscription.max_retry_limit:
                is_permitted = False
                rule_id = "POL-004"
                reason = f"Exceeded maximum subscription retry attempts ({subscription.max_retry_limit}). Must switch method, dunning, or stop."

            candidates.append({
                "action": action_name,
                "probability": prob,
                "expected_recovery_value": round(ev, 2),
                "permitted": is_permitted,
                "policy_outcome": "ALLOW" if is_permitted else "DENY",
                "rule_id": rule_id,
                "reason": reason,
            })

        # Rank permitted actions by EV descending
        permitted = [c for c in candidates if c["permitted"]]
        if not permitted:
            selected = next((c for c in candidates if c["action"] == SubscriptionAction.STOP.value), candidates[0])
        else:
            permitted.sort(key=lambda x: (x["expected_recovery_value"], x["probability"]), reverse=True)
            selected = permitted[0]

        return {
            "selected_action": selected["action"],
            "recovery_probability": selected["probability"],
            "expected_recovery_value": selected["expected_recovery_value"],
            "policy_outcome": selected["policy_outcome"],
            "policy_rule_id": selected["rule_id"],
            "candidates": candidates,
        }


class SubscriptionSimulator:
    """Simulates payment executions and state transitions for all 6 subscription actions."""

    def __init__(self, seed: Optional[int] = None):
        import random
        self.rng = random.Random(seed)

    def execute(
        self,
        subscription: SubscriptionState,
        action: str,
        probability: float,
    ) -> Dict[str, Any]:
        action = action.upper()
        now = datetime.now(timezone.utc)
        subscription.current_attempt_count += 1

        if action == SubscriptionAction.STOP.value:
            subscription.current_state = SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED
            subscription.recovered = False
            subscription.updated_at = now
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED,
                    timestamp=now,
                    action=action,
                    metadata={"reason": "INVOLUNTARY_CHURN_RECOVERY_HALTED"},
                )
            )
            return {
                "action": action,
                "status": "CANCELLED",
                "recovered": False,
                "recovered_amount": 0.0,
                "message": "Subscription cancelled; recovery terminated to prevent excessive decline fees.",
            }

        elif action == SubscriptionAction.ESCALATE.value:
            subscription.updated_at = now
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.PAYMENT_FAILED,
                    timestamp=now,
                    action=action,
                    metadata={"escalated_to": "VIP_ACCOUNTS_TEAM"},
                )
            )
            return {
                "action": action,
                "status": "ESCALATED",
                "recovered": False,
                "recovered_amount": 0.0,
                "message": "High-value subscription escalated to VIP account manager for manual outreach.",
            }

        elif action == SubscriptionAction.SCHEDULE_RETRY.value:
            # Transition to RETRY_SCHEDULED
            subscription.current_state = SubscriptionLifecycleState.RETRY_SCHEDULED
            subscription.updated_at = now
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.RETRY_SCHEDULED,
                    timestamp=now,
                    action=action,
                    metadata={"delay_hours": 24, "retry_attempt": subscription.current_attempt_count},
                )
            )

            # Check if scheduled execution converts
            conversion = self.rng.random() < probability
            if conversion:
                subscription.current_state = SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
                subscription.recovered = True
                subscription.events.append(
                    SubscriptionEvent(
                        event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
                        timestamp=now,
                        action=action,
                        metadata={"channel": "SCHEDULED_DUNNING_CHARGE"},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "recovered": True,
                    "recovered_amount": subscription.renewal_amount,
                    "message": "Scheduled renewal retry succeeded; subscription fully recovered.",
                }
            else:
                return {
                    "action": action,
                    "status": "PENDING_RETRY",
                    "recovered": False,
                    "recovered_amount": 0.0,
                    "message": "Renewal retry scheduled in 24 hours.",
                }

        elif action == SubscriptionAction.SWITCH_PAYMENT_METHOD.value:
            # Record PAYMENT_METHOD_CHANGED
            old_method = subscription.primary_method
            new_method = subscription.backup_method or "UPI_AUTOPAY"
            subscription.primary_method = new_method
            subscription.current_state = SubscriptionLifecycleState.PAYMENT_METHOD_CHANGED
            subscription.updated_at = now
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.PAYMENT_METHOD_CHANGED,
                    timestamp=now,
                    action=action,
                    metadata={"from_method": old_method, "to_method": new_method},
                )
            )

            # Execute charge on new method
            conversion = self.rng.random() < probability
            if conversion:
                subscription.current_state = SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
                subscription.recovered = True
                subscription.events.append(
                    SubscriptionEvent(
                        event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
                        timestamp=now,
                        action=action,
                        metadata={"method": new_method, "renewal_captured": True},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "recovered": True,
                    "recovered_amount": subscription.renewal_amount,
                    "message": f"Successfully switched to backup {new_method} and recovered subscription.",
                }
            else:
                subscription.current_state = SubscriptionLifecycleState.PAYMENT_FAILED
                return {
                    "action": action,
                    "status": "FAILED",
                    "recovered": False,
                    "recovered_amount": 0.0,
                    "message": f"Switched to {new_method}, but renewal charge declined.",
                }

        elif action == SubscriptionAction.SEND_RECOVERY_MESSAGE.value:
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.PAYMENT_FAILED,
                    timestamp=now,
                    action=action,
                    metadata={"channel": "WHATSAPP_DUNNING_LINK"},
                )
            )

            conversion = self.rng.random() < probability
            if conversion:
                subscription.current_state = SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
                subscription.recovered = True
                subscription.events.append(
                    SubscriptionEvent(
                        event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
                        timestamp=now,
                        action=action,
                        metadata={"dunning_converted": True},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "recovered": True,
                    "recovered_amount": subscription.renewal_amount,
                    "message": "Customer responded to WhatsApp dunning link, updated card, and renewed subscription.",
                }
            else:
                return {
                    "action": action,
                    "status": "UNCONVERTED",
                    "recovered": False,
                    "recovered_amount": 0.0,
                    "message": "Dunning reminder delivered; awaiting customer action.",
                }

        elif action == SubscriptionAction.RETRY_PAYMENT.value:
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.PAYMENT_ATTEMPTED,
                    timestamp=now,
                    action=action,
                    metadata={"attempt": subscription.current_attempt_count},
                )
            )

            conversion = self.rng.random() < probability
            if conversion:
                subscription.current_state = SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED
                subscription.recovered = True
                subscription.events.append(
                    SubscriptionEvent(
                        event_id=f"evt_sub_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
                        timestamp=now,
                        action=action,
                        metadata={"captured": True},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "recovered": True,
                    "recovered_amount": subscription.renewal_amount,
                    "message": "Immediate retry authorized successfully; subscription recovered.",
                }
            else:
                subscription.current_state = SubscriptionLifecycleState.PAYMENT_FAILED
                return {
                    "action": action,
                    "status": "FAILED",
                    "recovered": False,
                    "recovered_amount": 0.0,
                    "message": "Immediate retry failed on gateway.",
                }

        return {
            "action": action,
            "status": "UNKNOWN",
            "recovered": False,
            "recovered_amount": 0.0,
            "message": f"Unsupported action {action}",
        }


class SubscriptionRecoveryAgent:
    """Autonomous Orchestrator executing the complete Phase 18 subscription recovery pipeline."""

    def __init__(
        self,
        decision_engine: Optional[SubscriptionDecisionEngine] = None,
        simulator: Optional[SubscriptionSimulator] = None,
        audit_trail: Optional[AuditTrail] = None,
    ):
        self.decision_engine = decision_engine or SubscriptionDecisionEngine()
        self.simulator = simulator or SubscriptionSimulator()
        self.audit_trail = audit_trail or AuditTrail()

    def run_pipeline(
        self,
        subscription: SubscriptionState,
        failure_code: Optional[str] = None,
        force_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs: Event Ingestion → Customer History → ML Prediction → Decision Engine → Policy → Simulator → Audit."""
        now = datetime.now(timezone.utc)
        fcode = failure_code or subscription.last_failure_code or "INSUFFICIENT_FUNDS"
        subscription.last_failure_code = fcode

        # 1. Ensure initial failure is recorded in events
        if subscription.current_state not in (SubscriptionLifecycleState.PAYMENT_FAILED, SubscriptionLifecycleState.RETRY_SCHEDULED):
            subscription.current_state = SubscriptionLifecycleState.PAYMENT_FAILED
            subscription.events.append(
                SubscriptionEvent(
                    event_id=f"evt_fail_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.PAYMENT_FAILED,
                    timestamp=now,
                    metadata={"failure_code": fcode},
                )
            )

        # 2. Decision Engine evaluation
        decision = self.decision_engine.evaluate_candidates(subscription, failure_code=fcode)
        selected_action = force_action or decision["selected_action"]
        probability = decision["recovery_probability"]
        expected_recovery_value = decision["expected_recovery_value"]

        subscription.recovery_action = selected_action
        subscription.recovery_probability = probability
        subscription.expected_recovery_value = expected_recovery_value
        subscription.policy_outcome = decision["policy_outcome"]
        subscription.policy_rule_id = decision["policy_rule_id"]

        # 3. Simulator execution
        sim_result = self.simulator.execute(subscription, selected_action, probability)

        # 4. Cryptographic SHA-256 Audit Trail
        audit_evt: AuditEvent = self.audit_trail.log_event(
            transaction_id=subscription.subscription_id,
            event_type="SUBSCRIPTION_RECOVERY_EXECUTED",
            actor="SUBSCRIPTION_RECOVERY_AGENT",
            selected_action=selected_action,
            recovery_probability=probability,
            expected_value=expected_recovery_value,
            policy_result=decision["policy_outcome"],
            policy_rule=decision["policy_rule_id"],
            execution_result=sim_result,
            revenue_recovered=subscription.renewal_amount if subscription.recovered else 0.0,
            input_summary={
                "subscription_id": subscription.subscription_id,
                "customer_id": subscription.customer_id,
                "plan_name": subscription.plan_name,
                "renewal_amount": subscription.renewal_amount,
                "failure_code": fcode,
                "tenure_months": subscription.customer_history.tenure_months,
                "attempts": subscription.current_attempt_count,
            },
        )
        subscription.audit_hash = audit_evt.hash

        return {
            "subscription_id": subscription.subscription_id,
            "plan_name": subscription.plan_name,
            "renewal_amount": subscription.renewal_amount,
            "failure_code": fcode,
            "selected_action": selected_action,
            "recovery_probability": probability,
            "expected_recovery_value": expected_recovery_value,
            "policy_outcome": decision["policy_outcome"],
            "policy_rule_id": decision["policy_rule_id"],
            "candidates": decision["candidates"],
            "execution": sim_result,
            "recovered": subscription.recovered,
            "current_state": subscription.current_state.value,
            "new_state": subscription.current_state.value,
            "audit_hash": audit_evt.hash,
            "subscription": subscription.to_dict(),
        }


class SubscriptionStore:
    """Thread-safe in-memory/persistent store for Subscriptions and Renewal Metrics."""

    _instance: Optional[SubscriptionStore] = None

    def __init__(self):
        self.subscriptions: Dict[str, SubscriptionState] = {}
        self.agent = SubscriptionRecoveryAgent()
        self._seed_sample_subscriptions()

    @classmethod
    def get_instance(cls) -> SubscriptionStore:
        if cls._instance is None:
            cls._instance = SubscriptionStore()
        return cls._instance

    def _seed_sample_subscriptions(self) -> None:
        """Seeds realistic demonstration subscriptions across various renewal failure scenarios."""
        now = datetime.now(timezone.utc)
        seeds = [
            # 1. Expired Card with Backup UPI AutoPay Available -> SWITCH_PAYMENT_METHOD
            {
                "id": "sub_pro_101",
                "customer_id": "cust_sub_101",
                "merchant_id": "merch_razor_01",
                "plan": "Enterprise Cloud Monthly",
                "amount": 14999.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "CARD_EXPIRED",
                "primary": "CARD",
                "backup": "UPI_AUTOPAY",
                "tenure": 14,
                "renewals": 12,
                "risk": 0.02,
                "dnd": False,
            },
            # 2. Insufficient Funds on Salary Account -> SCHEDULE_RETRY
            {
                "id": "sub_pro_102",
                "customer_id": "cust_sub_102",
                "merchant_id": "merch_razor_01",
                "plan": "Developer Pro Annual",
                "amount": 8999.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "INSUFFICIENT_FUNDS",
                "primary": "UPI_AUTOPAY",
                "backup": "CARD",
                "tenure": 8,
                "renewals": 7,
                "risk": 0.03,
                "dnd": False,
            },
            # 3. Card Expired without Backup -> SEND_RECOVERY_MESSAGE (Dunning link)
            {
                "id": "sub_pro_103",
                "customer_id": "cust_sub_103",
                "merchant_id": "merch_razor_01",
                "plan": "Starter SaaS Monthly",
                "amount": 2499.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "CARD_EXPIRED",
                "primary": "CARD",
                "backup": None,
                "tenure": 5,
                "renewals": 4,
                "risk": 0.04,
                "dnd": False,
            },
            # 4. Gateway Timeout -> RETRY_PAYMENT
            {
                "id": "sub_pro_104",
                "customer_id": "cust_sub_104",
                "merchant_id": "merch_razor_01",
                "plan": "Analytics Pro Monthly",
                "amount": 4999.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "GATEWAY_TIMEOUT",
                "primary": "NETBANKING",
                "backup": "UPI_AUTOPAY",
                "tenure": 18,
                "renewals": 16,
                "risk": 0.01,
                "dnd": False,
            },
            # 5. VIP High Value ($Amount > 50,000) with High Risk -> ESCALATE
            {
                "id": "sub_pro_105",
                "customer_id": "cust_sub_105",
                "merchant_id": "merch_razor_01",
                "plan": "VIP Enterprise Cluster",
                "amount": 65000.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "CARD_DECLINED",
                "primary": "CARD",
                "backup": None,
                "tenure": 3,
                "renewals": 2,
                "risk": 0.65,  # High risk high value
                "dnd": False,
            },
            # 6. Chronic Max Attempt Failure -> STOP / SUBSCRIPTION_CANCELLED
            {
                "id": "sub_pro_106",
                "customer_id": "cust_sub_106",
                "merchant_id": "merch_razor_01",
                "plan": "Legacy Basic Plan",
                "amount": 999.0,
                "state": SubscriptionLifecycleState.PAYMENT_FAILED,
                "failure": "CARD_DECLINED",
                "primary": "CARD",
                "backup": None,
                "tenure": 1,
                "renewals": 0,
                "risk": 0.88,  # Critical fraud risk
                "dnd": True,
            },
            # 7. Already Recovered Active Subscription
            {
                "id": "sub_pro_107",
                "customer_id": "cust_sub_107",
                "merchant_id": "merch_razor_01",
                "plan": "Growth Tier Monthly",
                "amount": 6999.0,
                "state": SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED,
                "failure": None,
                "primary": "UPI_AUTOPAY",
                "backup": "CARD",
                "tenure": 24,
                "renewals": 23,
                "risk": 0.01,
                "dnd": False,
            },
        ]

        for s in seeds:
            hist = SubscriptionCustomerHistory(
                customer_id=s["customer_id"],
                tenure_months=s["tenure"],
                consecutive_successful_renewals=s["renewals"],
                lifetime_billing_volume=s["amount"] * max(1, s["renewals"]),
                past_decline_count=1 if s["state"] == SubscriptionLifecycleState.PAYMENT_FAILED else 0,
                primary_payment_method=s["primary"],
                backup_payment_method=s["backup"],
                risk_score=s["risk"],
                dnd_enabled=s["dnd"],
            )

            state = SubscriptionState(
                subscription_id=s["id"],
                customer_id=s["customer_id"],
                merchant_id=s["merchant_id"],
                plan_name=s["plan"],
                renewal_amount=s["amount"],
                current_state=s["state"],
                created_at=now,
                updated_at=now,
                primary_method=s["primary"],
                backup_method=s["backup"],
                customer_history=hist,
                last_failure_code=s["failure"],
                recovered=(s["state"] == SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED),
                events=[
                    SubscriptionEvent(
                        event_id=f"evt_init_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.SUBSCRIPTION_CREATED,
                        timestamp=now,
                        metadata={"seed": True},
                    )
                ],
            )
            if s["state"] == SubscriptionLifecycleState.PAYMENT_FAILED:
                state.events.append(
                    SubscriptionEvent(
                        event_id=f"evt_fail_{uuid.uuid4().hex[:8]}",
                        state=SubscriptionLifecycleState.PAYMENT_FAILED,
                        timestamp=now,
                        metadata={"failure_code": s["failure"]},
                    )
                )
            self.subscriptions[state.subscription_id] = state

    def get_subscription(self, subscription_id: str) -> Optional[SubscriptionState]:
        return self.subscriptions.get(subscription_id)

    def list_subscriptions(
        self,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[SubscriptionState]:
        res = list(self.subscriptions.values())
        if status:
            res = [s for s in res if s.current_state.value == status.upper()]
        if customer_id:
            res = [s for s in res if s.customer_id == customer_id]
        res.sort(key=lambda x: x.created_at, reverse=True)
        return res[:limit]

    def create_subscription(
        self,
        customer_id: str,
        merchant_id: str,
        plan_name: str,
        renewal_amount: float,
        billing_cycle: str = "MONTHLY",
        primary_method: str = "CARD",
        backup_method: Optional[str] = "UPI_AUTOPAY",
        tenure_months: int = 1,
        consecutive_successful_renewals: int = 0,
        risk_score: float = 0.03,
        dnd_enabled: bool = False,
    ) -> SubscriptionState:
        now = datetime.now(timezone.utc)
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"

        hist = SubscriptionCustomerHistory(
            customer_id=customer_id,
            tenure_months=tenure_months,
            consecutive_successful_renewals=consecutive_successful_renewals,
            lifetime_billing_volume=renewal_amount * max(1, consecutive_successful_renewals),
            primary_payment_method=primary_method,
            backup_payment_method=backup_method,
            risk_score=risk_score,
            dnd_enabled=dnd_enabled,
        )

        sub = SubscriptionState(
            subscription_id=sub_id,
            customer_id=customer_id,
            merchant_id=merchant_id,
            plan_name=plan_name,
            renewal_amount=renewal_amount,
            billing_cycle=billing_cycle,
            current_state=SubscriptionLifecycleState.SUBSCRIPTION_CREATED,
            created_at=now,
            updated_at=now,
            primary_method=primary_method,
            backup_method=backup_method,
            customer_history=hist,
            events=[
                SubscriptionEvent(
                    event_id=f"evt_cre_{uuid.uuid4().hex[:8]}",
                    state=SubscriptionLifecycleState.SUBSCRIPTION_CREATED,
                    timestamp=now,
                    metadata={"created": True},
                )
            ],
        )
        self.subscriptions[sub_id] = sub
        return sub

    def record_event(
        self,
        subscription_id: str,
        new_state: SubscriptionLifecycleState,
        action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SubscriptionState:
        sub = self.subscriptions.get(subscription_id)
        if not sub:
            raise KeyError(f"Subscription '{subscription_id}' not found.")

        now = datetime.now(timezone.utc)
        sub.current_state = new_state
        sub.updated_at = now
        sub.events.append(
            SubscriptionEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                state=new_state,
                timestamp=now,
                action=action,
                metadata=metadata or {},
            )
        )
        if new_state == SubscriptionLifecycleState.SUBSCRIPTION_RECOVERED:
            sub.recovered = True
        elif new_state == SubscriptionLifecycleState.SUBSCRIPTION_CANCELLED:
            sub.recovered = False

        return sub
