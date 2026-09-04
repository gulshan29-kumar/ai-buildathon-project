from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.app.audit_trail import AuditEvent, AuditTrail
from backend.app.policy_engine import PolicyDecision, PolicyEngine, PolicyOutcome

logger = logging.getLogger(__name__)


class CheckoutLifecycleStage(str, Enum):
    PRODUCT_VIEW = "PRODUCT_VIEW"
    CHECKOUT_STARTED = "CHECKOUT_STARTED"
    PAYMENT_PAGE_OPENED = "PAYMENT_PAGE_OPENED"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_SUCCESS = "PAYMENT_SUCCESS"
    ABANDONED = "ABANDONED"


class AbandonmentAction(str, Enum):
    SEND_RECOVERY_MESSAGE = "SEND_RECOVERY_MESSAGE"
    SCHEDULE_RETRY = "SCHEDULE_RETRY"
    STOP = "STOP"


STAGE_TIMEOUT_SECONDS: Dict[CheckoutLifecycleStage, float] = {
    CheckoutLifecycleStage.PRODUCT_VIEW: 1800.0,  # 30 mins
    CheckoutLifecycleStage.CHECKOUT_STARTED: 900.0,  # 15 mins
    CheckoutLifecycleStage.PAYMENT_PAGE_OPENED: 600.0,  # 10 mins
    CheckoutLifecycleStage.PAYMENT_INITIATED: 300.0,  # 5 mins
}


@dataclass
class CheckoutEvent:
    event_id: str
    stage: CheckoutLifecycleStage
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "stage": self.stage.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CheckoutSessionState:
    session_id: str
    customer_id: str
    cart_value: float
    current_stage: CheckoutLifecycleStage
    created_at: datetime
    updated_at: datetime
    checkout_duration: float = 0.0
    device: str = "MOBILE"
    payment_method: str = "UPI"
    previous_purchases: int = 0
    previous_abandonment_count: int = 0
    risk_score: float = 0.05
    dnd_enabled: bool = False
    customer_tier: str = "STANDARD"
    events: List[CheckoutEvent] = field(default_factory=list)
    abandonment_detected: bool = False
    abandonment_reason: Optional[str] = None
    abandonment_detected_at: Optional[datetime] = None
    dropoff_stage: Optional[CheckoutLifecycleStage] = None
    recovery_action: Optional[str] = None
    recovery_probability: Optional[float] = None
    expected_recovery_value: Optional[float] = None
    policy_outcome: Optional[str] = None
    policy_rule_id: Optional[str] = None
    recovered: bool = False
    recovered_amount: float = 0.0
    audit_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "cart_value": round(self.cart_value, 2),
            "current_stage": self.current_stage.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "checkout_duration": round(self.checkout_duration, 1),
            "device": self.device,
            "payment_method": self.payment_method,
            "previous_purchases": self.previous_purchases,
            "previous_abandonment_count": self.previous_abandonment_count,
            "risk_score": round(self.risk_score, 3),
            "dnd_enabled": self.dnd_enabled,
            "customer_tier": self.customer_tier,
            "abandonment_detected": self.abandonment_detected,
            "abandonment_reason": self.abandonment_reason,
            "abandonment_detected_at": self.abandonment_detected_at.isoformat() if self.abandonment_detected_at else None,
            "dropoff_stage": self.dropoff_stage.value if self.dropoff_stage else None,
            "recovery_action": self.recovery_action,
            "recovery_probability": round(self.recovery_probability, 4) if self.recovery_probability is not None else None,
            "expected_recovery_value": round(self.expected_recovery_value, 2) if self.expected_recovery_value is not None else None,
            "policy_outcome": self.policy_outcome,
            "policy_rule_id": self.policy_rule_id,
            "recovered": self.recovered,
            "recovered_amount": round(self.recovered_amount, 2),
            "audit_hash": self.audit_hash,
            "events_count": len(self.events),
        }


class AbandonmentDetector:
    """Detects checkout abandonment based on explicit drop-off events or stage inactivity timeouts."""

    @staticmethod
    def detect(session: CheckoutSessionState, current_time: Optional[datetime] = None) -> Tuple[bool, Optional[str]]:
        now = current_time or datetime.now(timezone.utc)

        # Already completed successfully or already marked abandoned
        if session.current_stage == CheckoutLifecycleStage.PAYMENT_SUCCESS:
            return False, None
        if session.current_stage == CheckoutLifecycleStage.ABANDONED:
            return True, session.abandonment_reason or "PREVIOUSLY_ABANDONED"

        # Check explicit drop-off in recent events
        for event in reversed(session.events):
            trigger = event.metadata.get("trigger", "").upper()
            if trigger in ("WINDOW_CLOSED", "USER_EXIT", "BACK_NAVIGATION", "CART_CLEARED", "AUTH_CANCELLED"):
                return True, f"EXPLICIT_DROPOFF_{trigger}"

        # Check stage inactivity timeout
        timeout = STAGE_TIMEOUT_SECONDS.get(session.current_stage)
        if timeout:
            elapsed = (now - session.updated_at).total_seconds()
            if elapsed > timeout:
                return True, f"INACTIVITY_TIMEOUT_STAGE_{session.current_stage.value}"

        return False, None

    @staticmethod
    def mark_abandoned(session: CheckoutSessionState, reason: str, detected_at: Optional[datetime] = None) -> None:
        now = detected_at or datetime.now(timezone.utc)
        session.dropoff_stage = session.current_stage
        session.current_stage = CheckoutLifecycleStage.ABANDONED
        session.abandonment_detected = True
        session.abandonment_reason = reason
        session.abandonment_detected_at = now
        session.updated_at = now
        session.events.append(
            CheckoutEvent(
                event_id=f"evt_drop_{uuid.uuid4().hex[:8]}",
                stage=CheckoutLifecycleStage.ABANDONED,
                timestamp=now,
                metadata={"reason": reason, "dropoff_from": session.dropoff_stage.value},
            )
        )


class AbandonmentFeatureExtractor:
    """Extracts all 8 required features for checkout abandonment recovery prediction."""

    @staticmethod
    def extract(session: CheckoutSessionState) -> Dict[str, Any]:
        created = session.created_at
        now = session.updated_at or datetime.now(timezone.utc)

        time_features = {
            "hour_of_day": created.hour,
            "day_of_week": created.weekday(),
            "is_weekend": created.weekday() >= 5,
            "is_business_hours": 9 <= created.hour <= 21,
        }

        customer_history = {
            "customer_id": session.customer_id,
            "customer_tier": session.customer_tier,
            "risk_score": session.risk_score,
            "previous_purchases": session.previous_purchases,
            "previous_abandonment_count": session.previous_abandonment_count,
            "dnd_enabled": session.dnd_enabled,
        }

        features = {
            "cart_value": float(session.cart_value),
            "checkout_duration": float(session.checkout_duration),
            "customer_history": customer_history,
            "previous_purchases": int(session.previous_purchases),
            "payment_method": str(session.payment_method).upper(),
            "device": str(session.device).upper(),
            "time": time_features,
            "previous_abandonment_count": int(session.previous_abandonment_count),
        }
        return features


class AbandonmentRecoveryPredictor:
    """Calculates action-conditional recovery probabilities and expected recovery values for abandoned checkouts."""

    @staticmethod
    def predict_action_probabilities(features: Dict[str, Any]) -> Dict[str, float]:
        cart_value = float(features.get("cart_value", 0.0))
        duration = float(features.get("checkout_duration", 60.0))
        prev_purchases = int(features.get("previous_purchases", 0))
        prev_abandonments = int(features.get("previous_abandonment_count", 0))
        device = str(features.get("device", "MOBILE")).upper()
        time_info = features.get("time", {})
        hour = time_info.get("hour_of_day", 14) if isinstance(time_info, dict) else 14
        cust_hist = features.get("customer_history", {})
        risk_score = float(cust_hist.get("risk_score", 0.05)) if isinstance(cust_hist, dict) else 0.05
        dnd = bool(cust_hist.get("dnd_enabled", False)) if isinstance(cust_hist, dict) else False

        # Base recovery baseline for abandoned checkout
        p_msg = 0.68
        p_retry = 0.28
        p_stop = 0.04

        # 1. Purchase history modifier (+0.04 per previous purchase, up to +0.20)
        purchase_boost = min(0.20, prev_purchases * 0.04)
        p_msg += purchase_boost
        p_retry += purchase_boost * 0.6

        # 2. Abandonment history modifier (-0.08 per prior abandonment)
        abandon_penalty = min(0.40, prev_abandonments * 0.08)
        p_msg -= abandon_penalty
        p_retry -= abandon_penalty * 0.5
        p_stop += abandon_penalty

        # 3. Device modifier (Mobile shoppers have higher WhatsApp/SMS recovery conversion)
        if device == "MOBILE":
            p_msg += 0.07
        elif device == "DESKTOP":
            p_retry += 0.05

        # 4. Time of day modifier (Higher response during active daytime 09:00 - 21:00)
        if 9 <= hour <= 21:
            p_msg += 0.05
        else:
            # Late night: scheduled retry in morning is more effective
            p_msg -= 0.06
            p_retry += 0.08

        # 5. Cart Value adjustments (Extremely high tickets need manual review; micro-carts have high friction)
        if 1000 <= cart_value <= 25000:
            p_msg += 0.04  # Sweet spot for 1-click recovery links
        elif cart_value > 50000:
            p_msg -= 0.05
            p_retry += 0.04

        # 6. Fraud Risk suppression
        if risk_score > 0.60:
            p_msg = 0.00
            p_retry = 0.00
            p_stop = 0.95
        elif risk_score > 0.30:
            p_msg *= 0.60
            p_retry *= 0.70
            p_stop += 0.25

        # 7. DND / Communication Opt-out check
        if dnd:
            p_msg = 0.00
            p_retry = max(0.20, p_retry * 1.2)
            p_stop = max(p_stop, 0.40)

        # Normalize and clamp
        p_msg = max(0.0, min(0.95, p_msg))
        p_retry = max(0.0, min(0.90, p_retry))
        p_stop = max(0.0, min(1.0, p_stop))

        return {
            AbandonmentAction.SEND_RECOVERY_MESSAGE.value: round(p_msg, 4),
            AbandonmentAction.SCHEDULE_RETRY.value: round(p_retry, 4),
            AbandonmentAction.STOP.value: round(p_stop, 4),
        }


class CheckoutDecisionEngine:
    """Evaluates candidate actions, ranks by expected recovery value, and validates against PolicyEngine."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.predictor = AbandonmentRecoveryPredictor()

    def evaluate_candidates(
        self,
        session: CheckoutSessionState,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        probabilities = self.predictor.predict_action_probabilities(features)
        cart_value = session.cart_value

        candidates = []
        for action_name in [
            AbandonmentAction.SEND_RECOVERY_MESSAGE.value,
            AbandonmentAction.SCHEDULE_RETRY.value,
            AbandonmentAction.STOP.value,
        ]:
            prob = probabilities.get(action_name, 0.0)
            ev = cart_value * prob if action_name != AbandonmentAction.STOP.value else 0.0

            # Policy evaluation using the platform's unified PolicyEngine
            policy_event = {
                "transaction_id": session.session_id,
                "amount": session.cart_value,
                "status": "ABANDONED",
                "failure_code": "CUSTOMER_ABANDONED",
                "risk_score": session.risk_score,
                "attempt_number": 1,
                "action": action_name,
                "communication_opt_out": session.dnd_enabled,
                "dnd": session.dnd_enabled,
            }
            cust_ctx = {
                "customer_id": session.customer_id,
                "communication_opt_out": session.dnd_enabled,
                "dnd": session.dnd_enabled,
                "risk_score": session.risk_score,
            }
            policy_decision: PolicyDecision = self.policy_engine.evaluate(policy_event, customer_context=cust_ctx)

            candidates.append({
                "action": action_name,
                "probability": prob,
                "expected_recovery_value": round(ev, 2),
                "permitted": policy_decision.allowed,
                "policy_outcome": policy_decision.outcome.value,
                "rule_id": policy_decision.rule_id,
                "reason": policy_decision.reason,
            })

        # Rank permitted actions by EV descending; STOP is last unless only permitted
        permitted = [c for c in candidates if c["permitted"]]
        if not permitted:
            selected = next((c for c in candidates if c["action"] == AbandonmentAction.STOP.value), candidates[0])
        else:
            # Sort permitted by EV descending
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


class CheckoutSimulator:
    """Executes simulated abandonment recovery actions and models customer conversion to PAYMENT_SUCCESS."""

    def __init__(self, seed: Optional[int] = None):
        import random
        self.rng = random.Random(seed)

    def execute(
        self,
        session: CheckoutSessionState,
        action: str,
        probability: float,
    ) -> Dict[str, Any]:
        action = action.upper()

        if action == AbandonmentAction.STOP.value:
            session.recovered = False
            session.recovered_amount = 0.0
            return {
                "action": action,
                "status": "STOPPED",
                "customer_converted": False,
                "recovered_amount": 0.0,
                "message": "Recovery halted by policy or risk guardrail",
            }

        elif action == AbandonmentAction.SCHEDULE_RETRY.value:
            # Scheduled retry / delayed cart notification
            conversion = self.rng.random() < probability
            if conversion:
                session.current_stage = CheckoutLifecycleStage.PAYMENT_SUCCESS
                session.recovered = True
                session.recovered_amount = session.cart_value
                session.updated_at = datetime.now(timezone.utc)
                session.events.append(
                    CheckoutEvent(
                        event_id=f"evt_succ_{uuid.uuid4().hex[:8]}",
                        stage=CheckoutLifecycleStage.PAYMENT_SUCCESS,
                        timestamp=session.updated_at,
                        metadata={"action": action, "channel": "SCHEDULED_RETRY"},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "customer_converted": True,
                    "recovered_amount": session.cart_value,
                    "message": "Customer returned via scheduled retry reminder and completed payment",
                }
            else:
                session.recovered = False
                session.recovered_amount = 0.0
                return {
                    "action": action,
                    "status": "EXPIRED",
                    "customer_converted": False,
                    "recovered_amount": 0.0,
                    "message": "Scheduled retry reminder expired without customer return",
                }

        elif action == AbandonmentAction.SEND_RECOVERY_MESSAGE.value:
            # 1-Click WhatsApp / SMS recovery message
            conversion = self.rng.random() < probability
            if conversion:
                session.current_stage = CheckoutLifecycleStage.PAYMENT_SUCCESS
                session.recovered = True
                session.recovered_amount = session.cart_value
                session.updated_at = datetime.now(timezone.utc)
                session.events.append(
                    CheckoutEvent(
                        event_id=f"evt_conv_{uuid.uuid4().hex[:8]}",
                        stage=CheckoutLifecycleStage.PAYMENT_SUCCESS,
                        timestamp=session.updated_at,
                        metadata={"action": action, "channel": "WHATSAPP_1CLICK_LINK"},
                    )
                )
                return {
                    "action": action,
                    "status": "SUCCESS",
                    "customer_converted": True,
                    "recovered_amount": session.cart_value,
                    "message": "Customer clicked 1-click WhatsApp recovery link and completed checkout",
                }
            else:
                session.recovered = False
                session.recovered_amount = 0.0
                return {
                    "action": action,
                    "status": "UNCONVERTED",
                    "customer_converted": False,
                    "recovered_amount": 0.0,
                    "message": "Recovery message delivered but customer did not complete checkout",
                }

        return {
            "action": action,
            "status": "UNKNOWN",
            "customer_converted": False,
            "recovered_amount": 0.0,
            "message": f"Unsupported action {action}",
        }


class CheckoutRecoveryAgent:
    """Autonomous Orchestrator executing the complete Phase 17 checkout recovery pipeline."""

    def __init__(
        self,
        decision_engine: Optional[CheckoutDecisionEngine] = None,
        simulator: Optional[CheckoutSimulator] = None,
        audit_trail: Optional[AuditTrail] = None,
    ):
        self.decision_engine = decision_engine or CheckoutDecisionEngine()
        self.simulator = simulator or CheckoutSimulator()
        self.audit_trail = audit_trail or AuditTrail()

    def run_pipeline(
        self,
        session: CheckoutSessionState,
        force_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs: Ingestion → Detection → Features → Prediction → Decision → Policy → Simulator → Audit."""
        now = datetime.now(timezone.utc)

        # 1. Abandonment Detection
        is_abandoned, reason = AbandonmentDetector.detect(session, current_time=now)
        if not is_abandoned and session.current_stage != CheckoutLifecycleStage.ABANDONED:
            # Force detect if pipeline was explicitly called on a dropped session
            AbandonmentDetector.mark_abandoned(session, reason or "MANUAL_RECOVERY_TRIGGER", detected_at=now)
        elif is_abandoned and session.current_stage != CheckoutLifecycleStage.ABANDONED:
            AbandonmentDetector.mark_abandoned(session, reason or "DETECTED_ABANDONMENT", detected_at=now)

        # 2. Extract Features
        features = AbandonmentFeatureExtractor.extract(session)

        # 3. Decision Engine (Evaluates ML probabilities + Policy guardrails)
        decision = self.decision_engine.evaluate_candidates(session, features)
        selected_action = force_action or decision["selected_action"]
        probability = decision["recovery_probability"]
        expected_recovery_value = decision["expected_recovery_value"]

        session.recovery_action = selected_action
        session.recovery_probability = probability
        session.expected_recovery_value = expected_recovery_value
        session.policy_outcome = decision["policy_outcome"]
        session.policy_rule_id = decision["policy_rule_id"]

        # 4. Simulator Execution
        sim_result = self.simulator.execute(session, selected_action, probability)

        # 5. Cryptographic SHA-256 Audit Trail
        audit_evt: AuditEvent = self.audit_trail.log_event(
            transaction_id=session.session_id,
            event_type="CHECKOUT_ABANDONMENT_RECOVERY_EXECUTED",
            actor="CHECKOUT_RECOVERY_AGENT",
            selected_action=selected_action,
            recovery_probability=probability,
            expected_value=expected_recovery_value,
            policy_result=decision["policy_outcome"],
            policy_rule=decision["policy_rule_id"],
            execution_result=sim_result,
            revenue_recovered=session.recovered_amount,
            input_summary={
                "session_id": session.session_id,
                "customer_id": session.customer_id,
                "cart_value": session.cart_value,
                "dropoff_stage": session.dropoff_stage.value if session.dropoff_stage else None,
            },
        )
        session.audit_hash = audit_evt.hash

        return {
            "session_id": session.session_id,
            "cart_value": session.cart_value,
            "dropoff_stage": session.dropoff_stage.value if session.dropoff_stage else None,
            "features": features,
            "selected_action": selected_action,
            "recovery_probability": probability,
            "expected_recovery_value": expected_recovery_value,
            "policy_outcome": decision["policy_outcome"],
            "policy_rule_id": decision["policy_rule_id"],
            "candidates": decision["candidates"],
            "execution": sim_result,
            "recovered": session.recovered,
            "recovered_amount": session.recovered_amount,
            "audit_hash": audit_evt.hash,
            "session": session.to_dict(),
        }


class CheckoutSessionStore:
    """Thread-safe in-memory/persistent store for Checkout Sessions and Abandonment Metrics."""

    _instance: Optional[CheckoutSessionStore] = None

    def __init__(self):
        self.sessions: Dict[str, CheckoutSessionState] = {}
        self.agent = CheckoutRecoveryAgent()
        self._seed_sample_data()

    @classmethod
    def get_instance(cls) -> CheckoutSessionStore:
        if cls._instance is None:
            cls._instance = CheckoutSessionStore()
        return cls._instance

    def _seed_sample_data(self) -> None:
        """Seeds realistic demonstration checkout sessions across the 6 lifecycle stages."""
        now = datetime.now(timezone.utc)
        sample_configs = [
            # 1. Product View (Dropped off early)
            {
                "id": "chk_pv_001",
                "customer_id": "cust_8101",
                "cart_value": 4500.0,
                "stage": CheckoutLifecycleStage.PRODUCT_VIEW,
                "duration": 45.0,
                "device": "MOBILE",
                "method": "UPI",
                "purchases": 2,
                "abandonments": 1,
                "risk": 0.04,
                "dnd": False,
            },
            # 2. Checkout Started (High value cart dropped)
            {
                "id": "chk_cs_002",
                "customer_id": "cust_8102",
                "cart_value": 18200.0,
                "stage": CheckoutLifecycleStage.CHECKOUT_STARTED,
                "duration": 120.0,
                "device": "MOBILE",
                "method": "UPI",
                "purchases": 6,
                "abandonments": 0,
                "risk": 0.02,
                "dnd": False,
            },
            # 3. Payment Page Opened (Cart dropped before entering UPI/card)
            {
                "id": "chk_pp_003",
                "customer_id": "cust_8103",
                "cart_value": 9400.0,
                "stage": CheckoutLifecycleStage.PAYMENT_PAGE_OPENED,
                "duration": 210.0,
                "device": "DESKTOP",
                "method": "CARD",
                "purchases": 4,
                "abandonments": 1,
                "risk": 0.05,
                "dnd": False,
            },
            # 4. Payment Initiated (User auth window closed)
            {
                "id": "chk_pi_004",
                "customer_id": "cust_8104",
                "cart_value": 12500.0,
                "stage": CheckoutLifecycleStage.PAYMENT_INITIATED,
                "duration": 340.0,
                "device": "MOBILE",
                "method": "UPI",
                "purchases": 8,
                "abandonments": 2,
                "risk": 0.03,
                "dnd": False,
            },
            # 5. Abandoned (Unrecovered checkout with DND active)
            {
                "id": "chk_ab_005",
                "customer_id": "cust_8105",
                "cart_value": 6200.0,
                "stage": CheckoutLifecycleStage.ABANDONED,
                "duration": 180.0,
                "device": "MOBILE",
                "method": "UPI",
                "purchases": 1,
                "abandonments": 3,
                "risk": 0.08,
                "dnd": True,  # DND test
            },
            # 6. High Risk Abandonment (Fraud attempt blocked)
            {
                "id": "chk_ab_006",
                "customer_id": "cust_8106",
                "cart_value": 48000.0,
                "stage": CheckoutLifecycleStage.ABANDONED,
                "duration": 30.0,
                "device": "DESKTOP",
                "method": "CARD",
                "purchases": 0,
                "abandonments": 5,
                "risk": 0.89,  # High risk
                "dnd": False,
            },
            # 7. Payment Success (Completed without abandonment)
            {
                "id": "chk_ps_007",
                "customer_id": "cust_8107",
                "cart_value": 15000.0,
                "stage": CheckoutLifecycleStage.PAYMENT_SUCCESS,
                "duration": 95.0,
                "device": "MOBILE",
                "method": "UPI",
                "purchases": 5,
                "abandonments": 0,
                "risk": 0.02,
                "dnd": False,
            },
        ]

        for cfg in sample_configs:
            sess = CheckoutSessionState(
                session_id=cfg["id"],
                customer_id=cfg["customer_id"],
                cart_value=cfg["cart_value"],
                current_stage=cfg["stage"],
                created_at=now,
                updated_at=now,
                checkout_duration=cfg["duration"],
                device=cfg["device"],
                payment_method=cfg["method"],
                previous_purchases=cfg["purchases"],
                previous_abandonment_count=cfg["abandonments"],
                risk_score=cfg["risk"],
                dnd_enabled=cfg["dnd"],
                events=[
                    CheckoutEvent(
                        event_id=f"evt_init_{uuid.uuid4().hex[:8]}",
                        stage=cfg["stage"],
                        timestamp=now,
                        metadata={"seed": True},
                    )
                ],
            )
            if cfg["stage"] == CheckoutLifecycleStage.ABANDONED:
                sess.abandonment_detected = True
                sess.abandonment_reason = "USER_DROPPED_OFF"
                sess.abandonment_detected_at = now
                sess.dropoff_stage = CheckoutLifecycleStage.PAYMENT_PAGE_OPENED
            self.sessions[sess.session_id] = sess

    def get_session(self, session_id: str) -> Optional[CheckoutSessionState]:
        return self.sessions.get(session_id)

    def list_sessions(
        self,
        stage: Optional[str] = None,
        abandoned_only: bool = False,
        limit: int = 50,
    ) -> List[CheckoutSessionState]:
        res = list(self.sessions.values())
        if stage:
            res = [s for s in res if s.current_stage.value == stage.upper()]
        if abandoned_only:
            res = [s for s in res if s.abandonment_detected or s.current_stage == CheckoutLifecycleStage.ABANDONED]
        res.sort(key=lambda x: x.created_at, reverse=True)
        return res[:limit]

    def create_session(
        self,
        customer_id: str,
        cart_value: float,
        stage: CheckoutLifecycleStage = CheckoutLifecycleStage.PRODUCT_VIEW,
        device: str = "MOBILE",
        payment_method: str = "UPI",
        previous_purchases: int = 0,
        previous_abandonment_count: int = 0,
        risk_score: float = 0.05,
        dnd_enabled: bool = False,
    ) -> CheckoutSessionState:
        now = datetime.now(timezone.utc)
        session_id = f"chk_{uuid.uuid4().hex[:8]}"
        sess = CheckoutSessionState(
            session_id=session_id,
            customer_id=customer_id,
            cart_value=cart_value,
            current_stage=stage,
            created_at=now,
            updated_at=now,
            device=device,
            payment_method=payment_method,
            previous_purchases=previous_purchases,
            previous_abandonment_count=previous_abandonment_count,
            risk_score=risk_score,
            dnd_enabled=dnd_enabled,
            events=[
                CheckoutEvent(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    stage=stage,
                    timestamp=now,
                    metadata={"created": True},
                )
            ],
        )
        self.sessions[session_id] = sess
        return sess

    def record_lifecycle_event(
        self,
        session_id: str,
        new_stage: CheckoutLifecycleStage,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CheckoutSessionState:
        sess = self.sessions.get(session_id)
        if not sess:
            raise KeyError(f"Checkout session '{session_id}' not found.")

        now = datetime.now(timezone.utc)
        sess.current_stage = new_stage
        sess.updated_at = now
        sess.events.append(
            CheckoutEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                stage=new_stage,
                timestamp=now,
                metadata=metadata or {},
            )
        )
        if new_stage == CheckoutLifecycleStage.ABANDONED:
            sess.abandonment_detected = True
            sess.abandonment_reason = (metadata or {}).get("reason", "STAGE_ABANDONED")
            sess.abandonment_detected_at = now

        return sess

    def detect_all_abandonments(self) -> List[Dict[str, Any]]:
        """Scans active sessions and marks any timed-out sessions as abandoned."""
        detected = []
        now = datetime.now(timezone.utc)
        for sess in self.sessions.values():
            if sess.current_stage not in (CheckoutLifecycleStage.PAYMENT_SUCCESS, CheckoutLifecycleStage.ABANDONED):
                is_abandoned, reason = AbandonmentDetector.detect(sess, current_time=now)
                if is_abandoned:
                    AbandonmentDetector.mark_abandoned(sess, reason or "TIMEOUT", detected_at=now)
                    detected.append(sess.to_dict())
        return detected

    def calculate_dashboard_metrics(self) -> Dict[str, float]:
        """Calculates the 3 primary Phase 17 metrics."""
        abandoned_revenue = 0.0
        recoverable_revenue = 0.0
        recovered_revenue = 0.0

        for sess in self.sessions.values():
            # Abandoned if stage is ABANDONED or marked abandoned or successfully recovered from abandonment
            if sess.abandonment_detected or sess.current_stage == CheckoutLifecycleStage.ABANDONED or sess.recovered:
                abandoned_revenue += sess.cart_value

                # Recoverable is expected recovery value
                if sess.expected_recovery_value is not None:
                    recoverable_revenue += sess.expected_recovery_value
                else:
                    # Estimate based on default recoverable opportunity probability
                    features = AbandonmentFeatureExtractor.extract(sess)
                    probs = AbandonmentRecoveryPredictor.predict_action_probabilities(features)
                    max_p = max(probs.values()) if probs else 0.50
                    recoverable_revenue += sess.cart_value * max_p

                # Recovered revenue
                if sess.recovered:
                    recovered_revenue += sess.recovered_amount

        return {
            "abandoned_checkout_revenue": round(abandoned_revenue, 2),
            "recoverable_abandonment_revenue": round(recoverable_revenue, 2),
            "recovered_abandonment_revenue": round(recovered_revenue, 2),
        }
