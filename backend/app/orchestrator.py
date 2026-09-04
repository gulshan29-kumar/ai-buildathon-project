from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypedDict

from backend.app.action_predictor import (
    SUPPORTED_ACTIONS,
    ActionRecoveryPredictor,
)
from backend.app.audit_trail import AuditTrail
from backend.app.decision_engine import DecisionEngine
from backend.app.failure_classifier import FailureClassifier
from backend.app.policy_engine import PolicyDecision, PolicyEngine
from backend.app.security.safe_tools import (
    InvalidToolParameterError,
    PolicyBypassAttemptError,
    SafeToolRegistry,
    UnauthorizedToolError,
)
from backend.app.simulator import PaymentSimulator, PolicyBlockedExecutionError

logger = logging.getLogger(__name__)


try:
    from langgraph.graph import END, START, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


class RecoveryAgentState(TypedDict, total=False):
    transaction_id: str
    event: Dict[str, Any]
    transaction: Dict[str, Any]
    customer_context: Dict[str, Any]
    payment_context: Dict[str, Any]
    available_payment_methods: List[str]
    root_cause: Dict[str, Any]
    ml_prediction: Dict[str, Any]
    action_probabilities: Dict[str, float]
    candidate_actions: List[Dict[str, Any]]
    policy_decision: Dict[str, Any]
    selected_action: str
    action_parameters: Dict[str, Any]
    execution_result: Dict[str, Any]
    monitoring_outcome: str  # RECOVERED, NEXT_ACTION, WAIT, STOP, ESCALATE
    step_count: int
    max_steps: int
    llm_enabled: bool
    fallback_mode: bool
    llm_response: Optional[str]
    errors: List[str]
    logs: List[Dict[str, Any]]


class AgentTools:
    """13 Tools available to the Agentic Recovery Orchestrator."""

    def __init__(
        self,
        simulator: Optional[PaymentSimulator] = None,
        policy_engine: Optional[PolicyEngine] = None,
        action_predictor: Optional[ActionRecoveryPredictor] = None,
    ):
        self.simulator = simulator or PaymentSimulator()
        self.policy_engine = policy_engine or PolicyEngine()
        self.action_predictor = action_predictor or ActionRecoveryPredictor()
        self.safe_registry = SafeToolRegistry(policy_engine=self.policy_engine, simulator=self.simulator)
        self.audit_events: List[Dict[str, Any]] = []

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 1: Retrieve transaction details."""
        try:
            return self.simulator.get_payment_status(transaction_id)["payment"]
        except KeyError:
            return {"transaction_id": transaction_id, "status": "UNKNOWN"}

    def get_customer_context(self, customer_id: str) -> Dict[str, Any]:
        """Tool 2: Retrieve customer context and preferences."""
        return {
            "customer_id": customer_id,
            "preferred_payment_method": "UPI",
            "risk_score": 0.05,
            "success_rate": 0.88,
            "communication_opt_out": False,
            "dnd": False,
        }

    def get_payment_context(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 3: Retrieve gateway and payment context."""
        return {
            "transaction_id": transaction_id,
            "gateway": "SIMULATED_GATEWAY",
            "flow_stage": "AUTHORIZATION",
            "previous_retry_count": 0,
            "available_methods": ["UPI", "CARD", "NETBANKING", "WALLET"],
        }

    def predict_recovery(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Tool 4: Predict general recoverability score."""
        prob = self.action_predictor.estimate_action_probability(transaction, "RETRY_PAYMENT")
        return {"recovery_probability": prob, "simulated": True}

    def get_action_probabilities(self, transaction: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Tool 5: Predict action-specific probabilities across all 6 recovery actions."""
        return self.action_predictor.evaluate_all(transaction)

    def check_policy(
        self,
        action: str,
        transaction: Dict[str, Any],
        customer_context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Tool 6: Evaluate deterministic policy rules for an action."""
        self.safe_registry.validate_tool_name(action)
        return self.safe_registry.evaluate_policy(
            action=action,
            transaction=transaction,
            customer_context=customer_context,
        )

    def retry_payment(self, transaction_id: str, delay_seconds: int = 0) -> Dict[str, Any]:
        """Tool 7: Safe payment retry through policy gate and simulator."""
        self.safe_registry.validate_parameters("RETRY_PAYMENT", {"delay_seconds": delay_seconds})
        txn = self.get_transaction(transaction_id)
        self.safe_registry.enforce_policy_gate("RETRY_PAYMENT", txn)
        return self.simulator.retry_payment(transaction_id, delay_seconds=delay_seconds)

    def switch_payment_method(self, transaction_id: str, new_payment_method: str) -> Dict[str, Any]:
        """Tool 8: Switch payment instrument and re-attempt recovery."""
        self.safe_registry.validate_parameters("SWITCH_PAYMENT_METHOD", {"new_payment_method": new_payment_method})
        txn = self.get_transaction(transaction_id)
        self.safe_registry.enforce_policy_gate("SWITCH_PAYMENT_METHOD", txn)
        return self.simulator.switch_payment_method(transaction_id, new_payment_method)

    def send_recovery_message(self, transaction_id: str, channel: str = "WHATSAPP") -> Dict[str, Any]:
        """Tool 9: Dispatch recovery link to customer."""
        self.safe_registry.validate_parameters("SEND_RECOVERY_MESSAGE", {"channel": channel})
        txn = self.get_transaction(transaction_id)
        self.safe_registry.enforce_policy_gate("SEND_RECOVERY_MESSAGE", txn)
        return self.simulator.send_recovery_message(transaction_id, channel=channel)

    def schedule_retry(self, transaction_id: str, delay_seconds: int = 300) -> Dict[str, Any]:
        """Tool 10: Schedule a delayed retry."""
        self.safe_registry.validate_parameters("SCHEDULE_RETRY", {"delay_seconds": delay_seconds})
        txn = self.get_transaction(transaction_id)
        self.safe_registry.enforce_policy_gate("SCHEDULE_RETRY", txn)
        return self.simulator.schedule_retry(transaction_id, delay_seconds=delay_seconds)

    def get_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """Tool 11: Inspect payment status and event timeline."""
        return self.simulator.get_payment_status(transaction_id)

    def execute_safe_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Executes an authorized tool enforcing the safe tool allowlist."""
        self.safe_registry.validate_tool_name(tool_name)
        func = getattr(self, tool_name, None)
        if not func or not callable(func):
            raise UnauthorizedToolError(f"Tool '{tool_name}' cannot be invoked directly.")
        return func(**kwargs)

    def escalate_case(self, transaction_id: str, reason: str, severity: str = "HIGH") -> Dict[str, Any]:
        """Tool 12: Escalate case to human risk operations."""
        audit_entry = {
            "case_id": f"esc_{uuid.uuid4().hex[:8]}",
            "transaction_id": transaction_id,
            "status": "ESCALATED",
            "reason": reason,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
        self.audit_events.append(audit_entry)
        return audit_entry

    def log_audit_event(self, event_type: str, transaction_id: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Tool 13: Log structured audit event."""
        entry = {
            "audit_id": f"aud_{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "transaction_id": transaction_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
        self.audit_events.append(entry)
        return entry


class RecoveryOrchestrator:
    """Agentic Recovery Orchestrator using LangGraph with deterministic fallback.
    
    CRITICAL SAFETY:
    The LLM must NEVER directly modify payment state.
    Every action passes strictly through Agent -> PolicyEngine -> Action Tool -> Simulator.
    """

    def __init__(
        self,
        tools: Optional[AgentTools] = None,
        llm_client: Optional[Callable[[str], str]] = None,
        max_steps: int = 10,
    ):
        self.tools = tools or AgentTools()
        self.decision_engine = DecisionEngine(
            policy_engine=self.tools.policy_engine,
            action_predictor=self.tools.action_predictor,
        )
        self.llm_client = llm_client
        self.max_steps = max_steps
        self.compiled_graph = self._build_graph() if LANGGRAPH_AVAILABLE else None

    # --- Node Handlers ---

    def node_event(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 1: EVENT - Normalize event and setup orchestrator state."""
        event = dict(state.get("event") or {})
        txn_id = str(event.get("transaction_id") or event.get("id") or f"txn_{uuid.uuid4().hex[:8]}")
        state["transaction_id"] = txn_id
        state["errors"] = state.get("errors", [])
        state["logs"] = state.get("logs", [])
        state["fallback_mode"] = state.get("fallback_mode", False)


        state["logs"].append({"node": "EVENT", "message": f"Ingested event for {txn_id}", "timestamp": datetime.now(timezone.utc).isoformat()})
        self.tools.log_audit_event("ORCHESTRATOR_EVENT_INGESTED", txn_id, {"event": event})
        AuditTrail.get_instance().log_event(
            transaction_id=txn_id,
            event_type="PAYMENT_FAILED",
            actor="SIMULATOR",
            input_summary={"amount": event.get("amount"), "failure_code": event.get("failure_code"), "status": "FAILED"},
        )
        return state

    def node_load_context(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 2: LOAD_CONTEXT - Retrieve customer, payment, and transaction contexts."""
        txn_id = state["transaction_id"]

        # If transaction was not in simulator, create it so tools can act on it
        txn = state.get("transaction")
        if not txn:
            try:
                txn = self.tools.get_transaction(txn_id)
                if txn.get("status") == "UNKNOWN":
                    ev = state.get("event", {})
                    # If already SUCCESS or HIGH_RISK, initialize as dictionary record
                    if ev.get("status") == "SUCCESS":
                        txn = dict(ev)
                        txn["transaction_id"] = txn_id
                    elif float(ev.get("risk_score", 0.05)) > 0.85 or ev.get("failure_code") == "HIGH_RISK":
                        txn = dict(ev)
                        txn["transaction_id"] = txn_id
                        txn["status"] = "FAILED"
                    else:
                        txn = self.tools.simulator.create_payment(
                            transaction_id=txn_id,
                            amount=float(ev.get("amount", 1000.0)),
                            failure_code=ev.get("failure_code"),
                            risk_score=float(ev.get("risk_score", 0.05)),
                            payment_method=ev.get("payment_method", "UPI"),
                            idempotency_key=ev.get("idempotency_key"),
                        )
            except Exception as e:
                state["errors"].append(f"Context initialization error: {e}")
                txn = dict(state.get("event", {}))
                txn["transaction_id"] = txn_id

        state["transaction"] = txn

        cust_id = str(txn.get("customer_id") or "cust_default")
        state["customer_context"] = state.get("customer_context") or self.tools.get_customer_context(cust_id)
        state["payment_context"] = state.get("payment_context") or self.tools.get_payment_context(txn_id)
        state["available_payment_methods"] = state.get("available_payment_methods") or ["UPI", "CARD", "NETBANKING", "WALLET"]

        state["logs"].append({"node": "LOAD_CONTEXT", "message": f"Loaded context for customer {cust_id}"})
        return state

    def node_root_cause(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 3: ROOT_CAUSE - Classify failure cause and determine investigation path."""
        txn = state.get("transaction", {})
        code = str(txn.get("failure_code") or state.get("event", {}).get("failure_code") or "").upper()

        classification = FailureClassifier.classify(code) if code else None
        if classification:
            state["root_cause"] = classification.to_dict()
        else:
            state["root_cause"] = {"failure_code": "UNKNOWN", "category": "TECHNICAL", "automatic_recovery": True}

        state["logs"].append({"node": "ROOT_CAUSE", "root_cause": state["root_cause"]})
        AuditTrail.get_instance().log_event(
            transaction_id=state["transaction_id"],
            event_type="ROOT_CAUSE_IDENTIFIED",
            actor="ORCHESTRATOR",
            root_cause=state["root_cause"],
            input_summary={"failure_code": code},
        )
        return state

    def node_ml_prediction(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 4: ML_PREDICTION - Predict general recoverability probability."""
        txn = state.get("transaction", {})
        prediction = self.tools.predict_recovery(txn)
        state["ml_prediction"] = prediction
        state["logs"].append({"node": "ML_PREDICTION", "prediction": prediction})
        AuditTrail.get_instance().log_event(
            transaction_id=state["transaction_id"],
            event_type="RECOVERY_PREDICTED",
            actor="ML_MODEL",
            recovery_probability=prediction.get("recovery_probability"),
            model_version="v1.2.0",
        )
        return state

    def node_action_analysis(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 5: ACTION_ANALYSIS - Compute action-conditional probabilities & expected values."""
        txn = state.get("transaction", {})
        candidate_evals = self.tools.get_action_probabilities(txn)
        state["candidate_actions"] = candidate_evals
        state["action_probabilities"] = {c["action"]: c["probability"] for c in candidate_evals}
        state["logs"].append({"node": "ACTION_ANALYSIS", "candidates_count": len(candidate_evals)})
        return state

    def node_policy_check(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 6: POLICY_CHECK - Evaluate candidate actions through PolicyEngine."""
        txn = state.get("transaction", {})
        cust = state.get("customer_context", {})

        for cand in state.get("candidate_actions", []):
            decision = self.tools.check_policy(cand["action"], txn, cust)
            cand["permitted"] = decision.allowed
            cand["policy_outcome"] = decision.outcome.value
            cand["rule_id"] = decision.rule_id
            cand["reason"] = decision.reason

        state["logs"].append({"node": "POLICY_CHECK", "message": "Policy checks evaluated for candidate actions"})
        AuditTrail.get_instance().log_event(
            transaction_id=state["transaction_id"],
            event_type="POLICY_CHECKED",
            actor="POLICY_ENGINE",
            candidate_actions=state.get("candidate_actions"),
        )
        return state


    def node_decision(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 7: DECISION - Select best permitted action with explainable reasoning."""
        state["step_count"] = state.get("step_count", 0) + 1

        # Check step limit
        if state["step_count"] >= state.get("max_steps", self.max_steps):
            state["selected_action"] = "STOP"
            state["action_parameters"] = {}
            state["monitoring_outcome"] = "STOP"
            state["logs"].append({"node": "DECISION", "message": "Maximum steps exceeded; stopping execution"})
            return state

        txn = state.get("transaction", {})
        cust = state.get("customer_context", {})
        pay_ctx = state.get("payment_context", {})
        action_probs = state.get("action_probabilities", {})
        available_methods = state.get("available_payment_methods", [])

        # Try LLM advisory if enabled and provided
        llm_selected: Optional[str] = None
        if self.llm_client and state.get("llm_enabled", True) and not state.get("fallback_mode", False):
            prompt = (
                f"Evaluate payment recovery for transaction {state['transaction_id']}:\n"
                f"Amount: ₹{txn.get('amount')}, Failure: {txn.get('failure_code')}, Risk: {txn.get('risk_score')}\n"
                f"Candidate actions: {json.dumps(action_probs)}\n"
                "Recommend the best action from [RETRY_PAYMENT, SWITCH_PAYMENT_METHOD, SEND_RECOVERY_MESSAGE, SCHEDULE_RETRY, ESCALATE, STOP] in JSON: {\"action\": \"...\"}"
            )
            try:
                raw_resp = self.llm_client(prompt)
                state["llm_response"] = raw_resp
                parsed = json.loads(raw_resp)
                if isinstance(parsed, dict) and "action" in parsed and parsed["action"] in SUPPORTED_ACTIONS:
                    candidate_action = parsed["action"]
                    # CRITICAL SAFETY GATE: Verify LLM suggestion passes policy check!
                    pol_check = self.tools.check_policy(candidate_action, txn, cust)
                    if pol_check.allowed:
                        llm_selected = candidate_action
                    else:
                        state["errors"].append(f"LLM recommended '{candidate_action}' which was blocked by policy: {pol_check.reason}")
                        state["fallback_mode"] = True
                else:
                    state["errors"].append("Malformed LLM response structure; falling back to deterministic engine.")
                    state["fallback_mode"] = True
            except Exception as e:
                state["errors"].append(f"LLM failure: {e}; falling back to deterministic engine.")
                state["fallback_mode"] = True

        # If LLM did not provide a permitted action, use deterministic DecisionEngine
        if not llm_selected:
            decision = self.decision_engine.decide(
                transaction=txn,
                customer_context=cust,
                payment_context=pay_ctx,
                action_probabilities=action_probs,
                available_payment_methods=available_methods,
            )
            state["selected_action"] = decision.selected_action
            state["action_parameters"] = decision.metadata.get("suggested_parameters", {})
            state["policy_decision"] = {
                "status": decision.policy_status,
                "reasoning": decision.reasoning_summary,
                "ev": decision.expected_recovery_value,
            }
        else:
            state["selected_action"] = llm_selected
            state["action_parameters"] = {}
            state["policy_decision"] = {"status": "PERMITTED_VIA_LLM_ADVISORY", "reasoning": "Selected by LLM advisory and verified by safety policy."}

        state["logs"].append({"node": "DECISION", "selected_action": state["selected_action"]})
        AuditTrail.get_instance().log_event(
            transaction_id=state["transaction_id"],
            event_type="ACTION_SELECTED",
            actor="AGENT" if not state.get("fallback_mode") else "DECISION_ENGINE",
            selected_action=state.get("selected_action"),
            expected_value=state.get("policy_decision", {}).get("ev"),
            candidate_actions=state.get("candidate_actions"),
            agent_version="v1.0.0",
        )
        return state

    def node_execute_action(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 8: EXECUTE_ACTION - Dispatches action strictly through policy gate to simulator."""
        act = state.get("selected_action", "STOP")
        txn_id = state["transaction_id"]
        params = state.get("action_parameters", {})

        # CRITICAL SAFETY: Validate policy again right before execution
        txn = state.get("transaction", {})
        cust = state.get("customer_context", {})

        try:
            if act == "RETRY_PAYMENT":
                delay = params.get("delay_seconds", 0)
                res = self.tools.retry_payment(txn_id, delay_seconds=delay)
            elif act == "SWITCH_PAYMENT_METHOD":
                new_method = params.get("suggested_method", "UPI")
                res = self.tools.switch_payment_method(txn_id, new_method)
            elif act == "SEND_RECOVERY_MESSAGE":
                channel = params.get("channel", "WHATSAPP")
                res = self.tools.send_recovery_message(txn_id, channel=channel)
            elif act == "SCHEDULE_RETRY":
                delay = params.get("delay_seconds", 300)
                res = self.tools.schedule_retry(txn_id, delay_seconds=delay)
            elif act == "ESCALATE":
                res = self.tools.escalate_case(txn_id, reason=state.get("policy_decision", {}).get("reasoning", "Risk escalation"))
            else:  # STOP or WAIT_AND_POLL
                res = {"transaction_id": txn_id, "action": act, "status": "HALTED", "simulated": True}

            state["execution_result"] = res
        except PolicyBlockedExecutionError as e:
            state["errors"].append(f"Policy denied execution: {e}")
            state["execution_result"] = {"error": "POLICY_BLOCKED", "detail": str(e), "simulated": True}
        except Exception as e:
            state["errors"].append(f"Simulator execution failure: {e}")
            state["execution_result"] = {"error": "SIMULATOR_FAILURE", "detail": str(e), "simulated": True}

        state["logs"].append({"node": "EXECUTE_ACTION", "action": act, "result": state.get("execution_result")})
        AuditTrail.get_instance().log_event(
            transaction_id=state["transaction_id"],
            event_type="ACTION_EXECUTED",
            actor="ACTION_TOOL",
            selected_action=act,
            execution_result=state.get("execution_result"),
        )
        return state

    def node_monitor_result(self, state: RecoveryAgentState) -> RecoveryAgentState:
        """Node 9: MONITOR_RESULT - Evaluates outcome (RECOVERED, NEXT_ACTION, WAIT, STOP, ESCALATE)."""
        res = state.get("execution_result", {})

        act = state.get("selected_action", "STOP")

        if res.get("error") == "POLICY_BLOCKED":
            state["monitoring_outcome"] = "STOP"
        elif res.get("error") == "SIMULATOR_FAILURE":
            state["monitoring_outcome"] = "ESCALATE"
        elif act == "ESCALATE" or res.get("status") == "ESCALATED":
            state["monitoring_outcome"] = "ESCALATE"
        elif res.get("status") == "SUCCESS" or res.get("current_status") == "SUCCESS":
            state["monitoring_outcome"] = "RECOVERED"
        elif res.get("status") == "SCHEDULED" or act in {"SCHEDULE_RETRY", "WAIT_AND_POLL"}:
            state["monitoring_outcome"] = "WAIT"
        elif act == "STOP":
            state["monitoring_outcome"] = "STOP"
        elif state["step_count"] < state.get("max_steps", self.max_steps):
            remaining_cands = [
                c for c in state.get("candidate_actions", [])
                if c.get("permitted") and c["action"] != act and c.get("expected_recovery_value", 0.0) > 0
            ]
            if remaining_cands:
                state["monitoring_outcome"] = "NEXT_ACTION"
            else:
                state["monitoring_outcome"] = "STOP"
        else:
            state["monitoring_outcome"] = "STOP"

        state["logs"].append({"node": "MONITOR_RESULT", "outcome": state["monitoring_outcome"]})

        outcome = state["monitoring_outcome"]
        txn = state.get("transaction", {})
        amount = float(txn.get("amount", state.get("event", {}).get("amount", 0.0)))

        if outcome == "RECOVERED":
            AuditTrail.get_instance().log_event(
                transaction_id=state["transaction_id"],
                event_type="PAYMENT_RECOVERED",
                actor="ORCHESTRATOR",
                revenue_recovered=amount,
                execution_result=res,
                selected_action=act,
            )
        elif outcome == "ESCALATE":
            AuditTrail.get_instance().log_event(
                transaction_id=state["transaction_id"],
                event_type="ESCALATED",
                actor="POLICY_ENGINE",
                execution_result=res,
                selected_action=act,
            )
        elif outcome == "STOP":
            AuditTrail.get_instance().log_event(
                transaction_id=state["transaction_id"],
                event_type="STOPPED",
                actor="POLICY_ENGINE",
                execution_result=res,
                selected_action=act,
            )
        elif res.get("status") == "FAILED":
            AuditTrail.get_instance().log_event(
                transaction_id=state["transaction_id"],
                event_type="RECOVERY_FAILED",
                actor="SIMULATOR",
                execution_result=res,
                selected_action=act,
            )

        return state


    # --- Graph Construction ---

    def _build_graph(self):
        """Constructs LangGraph StateGraph connecting all orchestrator nodes."""
        graph = StateGraph(RecoveryAgentState)

        graph.add_node("EVENT", self.node_event)
        graph.add_node("LOAD_CONTEXT", self.node_load_context)
        graph.add_node("ROOT_CAUSE", self.node_root_cause)
        graph.add_node("ML_PREDICTION", self.node_ml_prediction)
        graph.add_node("ACTION_ANALYSIS", self.node_action_analysis)
        graph.add_node("POLICY_CHECK", self.node_policy_check)
        graph.add_node("DECISION", self.node_decision)
        graph.add_node("EXECUTE_ACTION", self.node_execute_action)
        graph.add_node("MONITOR_RESULT", self.node_monitor_result)

        graph.add_edge(START, "EVENT")
        graph.add_edge("EVENT", "LOAD_CONTEXT")
        graph.add_edge("LOAD_CONTEXT", "ROOT_CAUSE")
        graph.add_edge("ROOT_CAUSE", "ML_PREDICTION")
        graph.add_edge("ML_PREDICTION", "ACTION_ANALYSIS")
        graph.add_edge("ACTION_ANALYSIS", "POLICY_CHECK")
        graph.add_edge("POLICY_CHECK", "DECISION")
        graph.add_edge("DECISION", "EXECUTE_ACTION")
        graph.add_edge("EXECUTE_ACTION", "MONITOR_RESULT")

        def route_monitoring(state: RecoveryAgentState):
            outcome = state.get("monitoring_outcome", "STOP")
            if outcome == "NEXT_ACTION" and state.get("step_count", 0) < state.get("max_steps", self.max_steps):
                return "ACTION_ANALYSIS"
            return END

        graph.add_conditional_edges(
            "MONITOR_RESULT",
            route_monitoring,
            {"ACTION_ANALYSIS": "ACTION_ANALYSIS", END: END},
        )

        return graph.compile()

    def run(self, event: Dict[str, Any], **kwargs) -> RecoveryAgentState:
        """Executes orchestration via LangGraph when available or deterministic engine as fallback."""
        initial_state: RecoveryAgentState = {
            "event": event,
            "transaction_id": str(event.get("transaction_id") or event.get("id") or f"txn_{uuid.uuid4().hex[:8]}"),
            "max_steps": kwargs.get("max_steps", self.max_steps),
            "llm_enabled": kwargs.get("llm_enabled", bool(self.llm_client)),
            "fallback_mode": kwargs.get("fallback_mode", False),
            "step_count": 0,
            "errors": [],
            "logs": [],
        }

        # If LangGraph is compiled and available, execute through it
        if self.compiled_graph:
            try:
                res = self.compiled_graph.invoke(initial_state)
                return res
            except Exception as e:
                logger.warning(f"LangGraph execution exception: {e}; routing through deterministic graph runner.")
                initial_state["errors"].append(f"LangGraph execution exception: {e}")
                initial_state["fallback_mode"] = True

        # Deterministic Graph Runner (Fallback Mode)
        state = dict(initial_state)
        state = self.node_event(state)
        state = self.node_load_context(state)
        state = self.node_root_cause(state)
        state = self.node_ml_prediction(state)

        while state.get("step_count", 0) < state.get("max_steps", self.max_steps):
            state = self.node_action_analysis(state)
            state = self.node_policy_check(state)
            state = self.node_decision(state)
            state = self.node_execute_action(state)
            state = self.node_monitor_result(state)

            if state.get("monitoring_outcome") != "NEXT_ACTION":
                break

        return state
