from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Set

from backend.app.action_predictor import SUPPORTED_ACTIONS
from backend.app.policy_engine import PolicyDecision, PolicyEngine
from backend.app.simulator import PaymentSimulator, PolicyBlockedExecutionError

logger = logging.getLogger("backend.app.security.safe_tools")


class SafeToolError(Exception):
    """Base exception for safe tool execution errors."""
    pass


class UnauthorizedToolError(SafeToolError):
    """Raised when an agent attempts to invoke a non-allowlisted tool or arbitrary function."""
    pass


class PolicyBypassAttemptError(SafeToolError):
    """Raised when an action attempts to execute without mandatory PolicyEngine validation."""
    pass


class InvalidToolParameterError(SafeToolError):
    """Raised when tool parameters violate security constraints or bounds."""
    pass


# Strict allowlist of authorized agent tool names
SAFE_READ_TOOLS: Set[str] = {
    "get_transaction",
    "get_customer_context",
    "get_payment_context",
    "predict_recovery",
    "get_action_probabilities",
    "check_policy",
    "get_payment_status",
}

SAFE_ACTION_TOOLS: Set[str] = (
    set(SUPPORTED_ACTIONS)
    | {act.lower() for act in SUPPORTED_ACTIONS}
    | {"escalate_case", "log_audit_event", "escalate", "ESCALATE", "stop", "STOP"}
)

ALL_AUTHORIZED_TOOLS: Set[str] = (
    SAFE_READ_TOOLS
    | SAFE_ACTION_TOOLS
    | {t.lower() for t in SAFE_READ_TOOLS}
    | {t.upper() for t in SAFE_READ_TOOLS}
)

ALLOWED_PAYMENT_METHODS: Set[str] = {"UPI", "CARD", "NETBANKING", "WALLET"}
ALLOWED_CHANNELS: Set[str] = {"WHATSAPP", "SMS", "EMAIL"}


class SafeToolRegistry:
    """Enforces Principle of Least Privilege and Non-Bypassable Policy Gates.
    
    Security Guarantees:
    1. Zero Arbitrary Code: Only allowlisted tools can be executed; dynamic reflection,
       eval, exec, and shell executions are strictly prohibited.
    2. Zero Policy Bypass: All mutating recovery actions MUST be validated by PolicyEngine.
       There are NO override flags, debug modes, or admin bypasses.
    3. Zero Direct State Mutation: The agent cannot directly alter payment status in
       the database or memory; state transitions occur strictly via verified simulator
       or gateway adapters.
    4. Strict Parameter Bounds: Enforces validated data types and numerical limits.
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        simulator: Optional[PaymentSimulator] = None,
    ):
        self.policy_engine = policy_engine or PolicyEngine()
        self.simulator = simulator or PaymentSimulator()

    @classmethod
    def is_tool_authorized(cls, tool_name: str) -> bool:
        """Verifies if the tool name belongs to the safe allowlist."""
        return tool_name.strip() in ALL_AUTHORIZED_TOOLS

    @classmethod
    def validate_tool_name(cls, tool_name: str) -> None:
        """Raises UnauthorizedToolError if the tool is not in the safe allowlist."""
        if not cls.is_tool_authorized(tool_name):
            logger.warning(
                f"[SECURITY ALERT] Unauthorized tool invocation attempted: '{tool_name}'"
            )
            raise UnauthorizedToolError(
                f"Access denied: Tool '{tool_name}' is not in the authorized agent tool registry."
            )

    def validate_parameters(self, tool_name: str, params: Dict[str, Any]) -> None:
        """Enforces type bounds, numerical limits, and allowed enum values."""
        if tool_name in ("retry_payment", "RETRY_PAYMENT", "schedule_retry", "SCHEDULE_RETRY"):
            delay = params.get("delay_seconds", 0)
            if not isinstance(delay, (int, float)) or delay < 0 or delay > 86400:
                raise InvalidToolParameterError(
                    f"delay_seconds must be between 0 and 86400 seconds (got: {delay})"
                )

        elif tool_name in ("switch_payment_method", "SWITCH_PAYMENT_METHOD"):
            method = str(params.get("new_payment_method") or params.get("suggested_method") or "").upper()
            if method and method not in ALLOWED_PAYMENT_METHODS:
                raise InvalidToolParameterError(
                    f"Payment method '{method}' is unauthorized. Allowed: {ALLOWED_PAYMENT_METHODS}"
                )

        elif tool_name in ("send_recovery_message", "SEND_RECOVERY_MESSAGE"):
            channel = str(params.get("channel", "WHATSAPP")).upper()
            if channel not in ALLOWED_CHANNELS:
                raise InvalidToolParameterError(
                    f"Communication channel '{channel}' is unauthorized. Allowed: {ALLOWED_CHANNELS}"
                )

    def evaluate_policy(
        self,
        action: str,
        transaction: Dict[str, Any],
        customer_context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Evaluates policy without raising execution error (used for planning and inspection)."""
        act_upper = action.upper().strip()
        if act_upper not in SUPPORTED_ACTIONS:
            raise UnauthorizedToolError(f"Action '{act_upper}' is not a recognized recovery action.")

        # Evaluate deterministic policy engine
        eval_payload = dict(transaction)
        eval_payload["action"] = act_upper

        previous_attempts = max(0, int(transaction.get("attempt_number", 1)) - 1)
        return self.policy_engine.evaluate(
            eval_payload,
            customer_context=customer_context,
            previous_attempts=previous_attempts,
        )

    def enforce_policy_gate(
        self,
        action: str,
        transaction: Dict[str, Any],
        customer_context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """Mandatory policy execution gate. Throws PolicyBlockedExecutionError if blocked."""
        decision = self.evaluate_policy(
            action=action,
            transaction=transaction,
            customer_context=customer_context,
        )

        if not decision.allowed:
            logger.warning(
                f"[GUARDRAIL ACTIVATED] Policy blocked action '{action}': {decision.reason} (Rule: {decision.rule_id})"
            )
            raise PolicyBlockedExecutionError(
                f"PolicyEngine DENIED action '{action}': {decision.reason} [Rule {decision.rule_id}]"
            )

        return decision

    def assert_no_direct_state_modification(self, target_obj: Any, field_name: str) -> None:
        """Asserts that the caller cannot directly overwrite payment status."""
        if field_name in ("status", "recovered", "amount"):
            raise SafeToolError(
                f"Agent violation: Direct modification of payment '{field_name}' is forbidden. "
                "Transitions must be executed through approved gateway adapters."
            )
