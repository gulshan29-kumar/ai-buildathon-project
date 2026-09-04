"""Security and safety modules for RazorRecover AI.

Provides:
- Prompt injection detection and input sanitization (prompt_guard)
- Safe tool execution and least privilege enforcement (safe_tools)
- Sensitive data and PII redaction for structured logging (redactor)
- Idempotency key tracking and replay attack prevention (idempotency)
- Sliding window rate limiting (rate_limiter)
- API authentication and authorization dependencies (auth)
"""

from backend.app.security.prompt_guard import (
    PromptInjectionDetectedError,
    PromptInjectionDetector,
    sanitize_prompt_input,
    wrap_untrusted_input,
)
from backend.app.security.safe_tools import (
    SafeToolError,
    SafeToolRegistry,
    UnauthorizedToolError,
)
from backend.app.security.redactor import (
    PIIFilter,
    SensitiveDataRedactor,
    mask_pii,
)
from backend.app.security.idempotency import (
    IdempotencyConflictError,
    IdempotencyManager,
    IdempotencyMismatchError,
    get_idempotency_manager,
)
from backend.app.security.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
    get_rate_limiter,
)
from backend.app.security.auth import verify_api_key

__all__ = [
    "PromptInjectionDetector",
    "PromptInjectionDetectedError",
    "sanitize_prompt_input",
    "wrap_untrusted_input",
    "SafeToolRegistry",
    "SafeToolError",
    "UnauthorizedToolError",
    "SensitiveDataRedactor",
    "PIIFilter",
    "mask_pii",
    "IdempotencyManager",
    "IdempotencyConflictError",
    "IdempotencyMismatchError",
    "get_idempotency_manager",
    "SlidingWindowRateLimiter",
    "RateLimitExceededError",
    "get_rate_limiter",
    "verify_api_key",
]
