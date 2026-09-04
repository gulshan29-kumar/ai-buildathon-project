from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("backend.app.security.rate_limiter")


class RateLimitExceededError(Exception):
    """Raised when client exceeds maximum allowable requests in sliding window (HTTP 429)."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class SlidingWindowRateLimiter:
    """Thread-safe In-Memory Sliding Window Rate Limiter."""

    _instance: Optional[SlidingWindowRateLimiter] = None
    _lock = threading.Lock()

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.windows: Dict[str, List[float]] = {}
        self._mutex = threading.Lock()

    @classmethod
    def get_instance(cls) -> SlidingWindowRateLimiter:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def check_limit(
        self,
        identifier: str,
        limit: int = 60,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """Checks if the identifier has exceeded `limit` requests in `window_seconds`.
        
        Returns:
            (allowed: bool, remaining_requests: int, retry_after_seconds: int)
        """
        if not self.enabled:
            return True, limit, 0

        now = time.time()
        window_start = now - window_seconds

        with self._mutex:
            history = self.windows.get(identifier, [])
            # Filter timestamps outside window
            valid_timestamps = [t for t in history if t > window_start]

            if len(valid_timestamps) >= limit:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(oldest + window_seconds - now))
                logger.warning(
                    f"[RATE LIMIT] Client '{identifier}' exceeded {limit} req/{window_seconds}s limit. Retry-After: {retry_after}s."
                )
                self.windows[identifier] = valid_timestamps
                return False, 0, retry_after

            # Within limits: record current request
            valid_timestamps.append(now)
            self.windows[identifier] = valid_timestamps
            remaining = max(0, limit - len(valid_timestamps))
            return True, remaining, 0

    def enforce(
        self,
        identifier: str,
        limit: int = 60,
        window_seconds: int = 60,
    ) -> None:
        """Enforces rate limit, raising RateLimitExceededError if exceeded."""
        allowed, remaining, retry_after = self.check_limit(
            identifier=identifier,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            raise RateLimitExceededError(
                f"Rate limit exceeded: Maximum {limit} requests per {window_seconds}s allowed. Please retry after {retry_after} seconds.",
                retry_after=retry_after,
            )

    def reset(self) -> None:
        """Clears all sliding windows (useful in tests)."""
        with self._mutex:
            self.windows.clear()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter.get_instance()
