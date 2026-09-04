from __future__ import annotations

import copy
import logging
import re
from typing import Any, Dict, List, Pattern, Union

logger = logging.getLogger("backend.app.security.redactor")

# Precompiled regex patterns for sensitive data
CARD_PAN_PATTERN: Pattern[str] = re.compile(
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b"
)
GENERIC_16_DIGIT_PATTERN: Pattern[str] = re.compile(
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?(\d{4})\b"
)
CVV_PATTERN: Pattern[str] = re.compile(
    r"(?i)\b(cvv|cvc|security[_-]?code)[\s:=]+([0-9]{3,4})\b"
)
AUTH_BEARER_PATTERN: Pattern[str] = re.compile(
    r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{15,}"
)
SECRET_KEY_PATTERN: Pattern[str] = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|password|access[_-]?token|auth[_-]?token)[\s:=]+[\"']?([a-zA-Z0-9_\-\.]{8,})[\"']?"
)
EMAIL_PATTERN: Pattern[str] = re.compile(
    r"\b([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b"
)
PHONE_PATTERN: Pattern[str] = re.compile(
    r"\b(?:\+?91[- ]?)?([6-9]\d{2})\d{3}(\d{4})\b"
)


def is_luhn_valid(card_number: str) -> bool:
    """Verifies Luhn checksum for a card number string."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


class SensitiveDataRedactor:
    """Detects and masks PII, payment card numbers, credentials, and secrets."""

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Redacts all sensitive tokens from a text string."""
        if not text or not isinstance(text, str):
            return text

        redacted = text

        # 1. Redact Bearer Tokens
        redacted = AUTH_BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", redacted)

        # 2. Redact API Keys, Secrets, Passwords
        def _mask_secret(match: re.Match) -> str:
            key_name = match.group(1)
            return f"{key_name}=[REDACTED_SECRET]"
        redacted = SECRET_KEY_PATTERN.sub(_mask_secret, redacted)

        # 3. Redact CVV / CVC
        def _mask_cvv(match: re.Match) -> str:
            label = match.group(1)
            return f"{label}=***"
        redacted = CVV_PATTERN.sub(_mask_cvv, redacted)

        # 4. Redact Credit Card PANs (16-digit card pattern)
        def _mask_pan(match: re.Match) -> str:
            last4 = match.group(1)
            return f"****-****-****-{last4}"
        redacted = GENERIC_16_DIGIT_PATTERN.sub(_mask_pan, redacted)

        # 5. Redact Email Addresses (e.g. user@example.com -> u***@example.com)
        def _mask_email(match: re.Match) -> str:
            first_char = match.group(1)
            domain = match.group(2)
            return f"{first_char}***@{domain}"
        redacted = EMAIL_PATTERN.sub(_mask_email, redacted)

        # 6. Redact Phone Numbers (e.g. +91 9876543210 -> +91-987***-3210)
        def _mask_phone(match: re.Match) -> str:
            prefix = match.group(1)
            suffix = match.group(2)
            return f"+91-{prefix}***-{suffix}"
        redacted = PHONE_PATTERN.sub(_mask_phone, redacted)

        return redacted

    @classmethod
    def redact_dict(cls, data: Union[Dict[str, Any], List[Any]]) -> Union[Dict[str, Any], List[Any]]:
        """Deeply traverses and redacts sensitive keys and values in a dictionary or list."""
        sensitive_keys = {
            "card_number", "pan", "cvv", "cvc", "security_code",
            "password", "secret", "api_key", "token", "access_token",
            "bearer_token", "private_key"
        }

        if isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                k_lower = str(k).lower()
                if k_lower in sensitive_keys:
                    clean_dict[k] = "[REDACTED]"
                elif isinstance(v, (dict, list)):
                    clean_dict[k] = cls.redact_dict(v)
                elif isinstance(v, str):
                    clean_dict[k] = cls.redact_text(v)
                else:
                    clean_dict[k] = v
            return clean_dict
        elif isinstance(data, list):
            return [cls.redact_dict(item) if isinstance(item, (dict, list))
                    else cls.redact_text(item) if isinstance(item, str)
                    else item for item in data]
        return data


def mask_pii(data: Any) -> Any:
    """Convenience helper for masking PII and secrets across strings, dicts, or objects."""
    if isinstance(data, str):
        return SensitiveDataRedactor.redact_text(data)
    elif isinstance(data, (dict, list)):
        return SensitiveDataRedactor.redact_dict(data)
    return data


class PIIFilter(logging.Filter):
    """Logging filter that redacts PII and secrets from all logger outputs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = SensitiveDataRedactor.redact_text(record.msg)
            if record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(
                        SensitiveDataRedactor.redact_text(str(a)) if isinstance(a, str) else a
                        for a in record.args
                    )
                elif isinstance(record.args, dict):
                    record.args = SensitiveDataRedactor.redact_dict(record.args)
        except Exception:
            # Never fail logging if filtering encounters unexpected structure
            pass
        return True
