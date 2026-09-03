from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field, field_validator, ValidationError

from backend.app.failure_classifier import (
    FailureCategory,
    FailureClassification,
    FailureClassifier,
    RecoverabilityLevel,
)

logger = logging.getLogger(__name__)


class RootCauseAnalysisResult(BaseModel):
    """Validated structured result for root cause analysis."""

    category: str = Field(..., description="Failure taxonomy category")
    reason: str = Field(..., description="Identified root cause reason")
    temporary: bool = Field(..., description="Whether the failure condition is temporary")
    recoverability: str = Field(..., description="Recoverability assessment (HIGH, MEDIUM, LOW, NONE)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    explanation: str = Field(..., description="Contextual explanation of failure cause and impact")
    deterministic_fallback_used: bool = Field(default=False, description="Whether deterministic fallback was used")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid_cats = {c.value for c in FailureCategory}
        val = v.upper().strip()
        if val not in valid_cats:
            return "TECHNICAL"
        return val

    @field_validator("recoverability")
    @classmethod
    def validate_recoverability(cls, v: str) -> str:
        valid_recs = {r.value for r in RecoverabilityLevel}
        val = v.upper().strip()
        if val not in valid_recs:
            return "LOW"
        return val

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class RootCauseAgent:
    """Agent that performs payment failure Root Cause Analysis.
    
    CRITICAL SAFETY & INTEGRITY:
    - Known failure codes use deterministic classification from FailureClassifier.
    - LLM may be used strictly for contextual reasoning, explanation, and summarization.
    - LLM must NEVER invent:
      * payment status (e.g. asserting successful payment when failed)
      * transaction amount
      * customer history
      * successful payment
    - All outputs are validated with Pydantic.
    - If LLM output is invalid, malformed, or violates hallucination guardrails,
      the agent seamlessly uses the deterministic fallback.
    """

    def __init__(self, llm_client: Optional[Callable[[str], str]] = None):
        self.llm_client = llm_client

    def _generate_deterministic_explanation(
        self,
        transaction: Dict[str, Any],
        failure_code: str,
        classification: FailureClassification,
        customer_context: Dict[str, Any],
        payment_context: Dict[str, Any],
    ) -> str:
        """Synthesizes a deterministic, fact-grounded explanation based on input data."""
        txn_id = transaction.get("transaction_id") or transaction.get("id") or "txn_unknown"
        amount = float(transaction.get("amount", payment_context.get("amount", 0.0)))
        method = transaction.get("payment_method") or payment_context.get("payment_method") or "UPI"
        gateway = transaction.get("gateway") or payment_context.get("gateway") or "payment gateway"
        risk_score = float(transaction.get("risk_score") or customer_context.get("risk_score", 0.05))

        code_upper = failure_code.upper()
        if code_upper == "GATEWAY_TIMEOUT":
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} via {method} failed due to a transient "
                f"network timeout with {gateway}. This is an infrastructure latency issue and "
                "is highly recoverable via automated retry."
            )
        elif code_upper == "CARD_EXPIRED":
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} failed because the provided payment card "
                "has passed its expiration date. Retrying the same card is impossible; recovery "
                "requires prompting the customer to select an alternative payment method."
            )
        elif code_upper == "INSUFFICIENT_FUNDS":
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} was declined by the issuer due to insufficient "
                "account balance. Immediate automated retries are ineffective; recovery requires customer "
                "notification or a scheduled retry window."
            )
        elif code_upper == "HIGH_RISK" or risk_score > 0.85:
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} was flagged with elevated fraud risk "
                f"(risk score: {risk_score:.2f}). In accordance with platform policy POL-003, "
                "automated recovery is strictly prohibited and the case is routed to human risk review."
            )
        elif code_upper == "CUSTOMER_ABANDONED":
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} was abandoned by the customer before completing "
                "the authentication challenge. Direct payment retry cannot execute; sending a recovery link "
                "via message (WhatsApp/SMS) is recommended."
            )
        elif code_upper == "DUPLICATE_PAYMENT":
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} was detected as a potential duplicate payment. "
                "To prevent double-charging the customer, automated execution has been halted under policy POL-002."
            )
        else:
            return (
                f"Transaction {txn_id} for ₹{amount:,.2f} via {method} failed with code '{failure_code}'. "
                f"Classification: category={classification.category.value}, temporary={classification.temporary}. "
                f"Recommended action: {classification.recommended_action}."
            )

    def _validate_hallucinations(
        self,
        llm_output: Dict[str, Any],
        transaction: Dict[str, Any],
        classification: FailureClassification,
        customer_context: Dict[str, Any],
        payment_context: Dict[str, Any],
    ) -> bool:
        """Validates that LLM output does NOT invent facts, successful payments, or amounts."""
        explanation = str(llm_output.get("explanation", ""))
        reason = str(llm_output.get("reason", ""))
        full_text = f"{explanation} {reason}".lower()

        # Guardrail 1: LLM must NOT invent successful payment
        real_status = str(transaction.get("status", payment_context.get("status", "FAILED"))).upper()
        if real_status != "SUCCESS":
            forbidden_success_patterns = [
                r"\bpayment (was|is) successful\b",
                r"\btransaction (was|is) successful\b",
                r"\bpayment succeeded\b",
                r"\btransaction succeeded\b",
                r"\balready paid\b",
                r"\bsuccessfully captured\b",
                r"\bpayment completed successfully\b",
            ]
            for pat in forbidden_success_patterns:
                if re.search(pat, full_text):
                    logger.warning(f"Hallucination detected: LLM asserted successful payment: '{pat}'")
                    return False

        # Guardrail 2: LLM must NOT invent/alter transaction amount
        actual_amount = float(transaction.get("amount", payment_context.get("amount", 0.0)))
        # Look for explicit currency assertions in the text, e.g. ₹99999 or $99999
        found_amounts = re.findall(r"(?:₹|\$|rs\.?|inr)\s*(\d+(?:,\d+)*(?:\.\d+)?)", full_text)
        for found_str in found_amounts:
            try:
                found_val = float(found_str.replace(",", ""))
                # If LLM asserted a specific amount differing significantly from actual amount
                if actual_amount > 0 and abs(found_val - actual_amount) > 1.0:
                    logger.warning(f"Hallucination detected: LLM invented amount {found_val} vs real {actual_amount}")
                    return False
            except ValueError:
                pass

        # Guardrail 3: LLM must NOT contradict deterministic category or temporality for known codes
        llm_category = str(llm_output.get("category", "")).upper()
        if llm_category and llm_category != classification.category.value:
            # Allow compatible categories, but reject outright contradictory classifications
            if classification.category in {FailureCategory.TEMPORARY, FailureCategory.RISK, FailureCategory.DUPLICATE}:
                if llm_category != classification.category.value:
                    logger.warning(f"LLM contradicted known category {classification.category.value} with {llm_category}")
                    return False

        return True

    def analyze(
        self,
        transaction: Optional[Dict[str, Any]] = None,
        failure_code: Optional[str] = None,
        customer_context: Optional[Dict[str, Any]] = None,
        payment_context: Optional[Dict[str, Any]] = None,
    ) -> RootCauseAnalysisResult:
        """Performs root cause analysis with deterministic grounding and LLM reasoning."""
        txn = dict(transaction or {})
        cust = dict(customer_context or {})
        pay_ctx = dict(payment_context or {})

        # Resolve failure code from explicit argument or contexts
        code = str(
            failure_code
            or txn.get("failure_code")
            or txn.get("failure_type")
            or pay_ctx.get("failure_code")
            or "UNKNOWN"
        ).strip().upper()

        # Step 1: Known failure codes must use deterministic classification
        classification = FailureClassifier.classify(code)
        if not classification:
            # Safe default classification for unknown code
            classification = FailureClassification(
                failure_code=code,
                category=FailureCategory.TECHNICAL,
                is_temporary=True,
                temporary_or_permanent="TEMPORARY",
                recoverability_level=RecoverabilityLevel.MEDIUM,
                automatic_recovery=True,
                recommended_action="RETRY_PAYMENT",
                recommended_investigation="Unrecognized failure code. Check gateway error logs.",
                requires_human_review=False,
            )

        # Baseline deterministic result
        deterministic_reason = classification.recommended_investigation
        deterministic_explanation = self._generate_deterministic_explanation(
            transaction=txn,
            failure_code=code,
            classification=classification,
            customer_context=cust,
            payment_context=pay_ctx,
        )

        fallback_result = RootCauseAnalysisResult(
            category=classification.category.value,
            reason=deterministic_reason,
            temporary=classification.temporary,
            recoverability=classification.recoverability,
            confidence=0.95,
            explanation=deterministic_explanation,
            deterministic_fallback_used=True,
        )

        # If no LLM client provided, return deterministic result immediately
        if not self.llm_client:
            return fallback_result

        # Step 2: Attempt LLM contextual reasoning & explanation enrichment
        txn_id = txn.get("transaction_id") or txn.get("id") or pay_ctx.get("order_id") or "txn_demo"
        amount = float(txn.get("amount", pay_ctx.get("amount", 0.0)))
        status = str(txn.get("status", pay_ctx.get("status", "FAILED"))).upper()
        risk = float(txn.get("risk_score") or cust.get("risk_score") or pay_ctx.get("risk_score", 0.05))

        prompt = (
            "You are an expert payment systems root cause analysis agent.\n"
            f"Analyze the payment failure for Transaction '{txn_id}':\n"
            f"- Exact Amount: ₹{amount:,.2f}\n"
            f"- Current Status: {status}\n"
            f"- Failure Code: {code}\n"
            f"- Deterministic Taxonomy Category: {classification.category.value}\n"
            f"- Temporary Condition: {classification.temporary}\n"
            f"- Recoverability Level: {classification.recoverability}\n"
            f"- Customer Context: {json.dumps(cust)}\n"
            f"- Payment Context: {json.dumps(pay_ctx)}\n\n"
            "STRICT RULES:\n"
            "1. Do NOT invent payment status (transaction status is FAILED).\n"
            "2. Do NOT invent or change the transaction amount.\n"
            "3. Do NOT claim the payment succeeded.\n"
            "4. Do NOT hallucinate past customer history not provided.\n\n"
            "Return JSON matching this exact schema:\n"
            "{\n"
            f'  "category": "{classification.category.value}",\n'
            '  "reason": "<specific concise technical cause>",\n'
            f'  "temporary": {str(classification.temporary).lower()},\n'
            f'  "recoverability": "{classification.recoverability}",\n'
            '  "confidence": 0.95,\n'
            '  "explanation": "<contextual explanation of why it failed and how customer context applies>"\n'
            "}"
        )

        try:
            raw_response = self.llm_client(prompt)
            # Clean possible markdown formatting
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            parsed = json.loads(cleaned)

            if not isinstance(parsed, dict):
                logger.warning("LLM returned non-dictionary JSON; falling back to deterministic.")
                return fallback_result

            # Check hallucination guardrails
            if not self._validate_hallucinations(parsed, txn, classification, cust, pay_ctx):
                logger.warning("LLM output violated hallucination guardrails; falling back to deterministic.")
                return fallback_result

            # Validate output using Pydantic
            validated = RootCauseAnalysisResult(
                category=str(parsed.get("category") or classification.category.value),
                reason=str(parsed.get("reason") or deterministic_reason),
                temporary=bool(parsed.get("temporary", classification.temporary)),
                recoverability=str(parsed.get("recoverability") or classification.recoverability),
                confidence=float(parsed.get("confidence", 0.95)),
                explanation=str(parsed.get("explanation") or deterministic_explanation),
                deterministic_fallback_used=False,
            )
            return validated

        except (json.JSONDecodeError, ValidationError, Exception) as e:
            logger.warning(f"LLM root cause analysis error ({e}); using deterministic fallback.")
            return fallback_result
