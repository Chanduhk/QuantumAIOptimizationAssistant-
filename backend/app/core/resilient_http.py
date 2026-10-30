from __future__ import annotations

import io
import logging
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Pattern to mask sensitive query params or headers
_SECRET_PATTERN = re.compile(r"(?i)(key|token|secret|password|auth|bearer)=([^&\s]+)")


def redact_secrets(text: str) -> str:
    """Mask credentials and tokens in URLs and error messages."""
    return _SECRET_PATTERN.sub(r"\1=***REDACTED***", text)


class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal operations
    OPEN = "open"            # Failing, rejecting requests immediately
    HALF_OPEN = "half_open"  # Testing recovery with a single probe request


@dataclass
class CircuitBreaker:
    """Bounded circuit breaker with cooldown recovery to isolate external API outages."""

    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    _lock: Lock = field(default_factory=Lock)

    def can_attempt(self) -> bool:
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            now = time.monotonic()
            if self.state == CircuitState.OPEN:
                if now - self.last_failure_time >= self.cooldown_seconds:
                    logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False
            # HALF_OPEN: allow probe
            return True

    def record_success(self) -> None:
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_success_time = time.monotonic()

    def record_failure(self, error: Exception) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.warning(
                        "Circuit breaker opened after %d failures. Outage cooldown %.1fs. Error: %s",
                        self.failure_count,
                        self.cooldown_seconds,
                        redact_secrets(str(error)),
                    )
                self.state = CircuitState.OPEN


class ResilientHttpClient:
    """Bounded retry client with exponential backoff, jitter, and circuit-breaker isolation."""

    def __init__(
        self,
        default_timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def is_transient_error(self, exc: Exception) -> bool:
        """Classify if an error is a transient network or server error worth retrying."""
        if isinstance(exc, (TimeoutError, urllib.error.URLError)):
            if isinstance(exc, urllib.error.HTTPError):
                # 429 Too Many Requests or 5xx Server Errors are transient
                return exc.code in {429, 500, 502, 503, 504}
            # Socket timeouts, connection resets, DNS resolution errors are transient
            return True
        return False

    def get_retry_after(self, exc: Exception) -> Optional[float]:
        """Extract Retry-After header if returned by the external service."""
        if isinstance(exc, urllib.error.HTTPError):
            headers = getattr(exc, "headers", None)
            if headers:
                retry_header = headers.get("Retry-After")
                if retry_header:
                    try:
                        return float(retry_header)
                    except (ValueError, TypeError):
                        pass
        return None

    def execute_request(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Execute HTTP request with circuit-breaker protection and bounded exponential backoff."""
        if not self.circuit_breaker.can_attempt():
            safe_url = redact_secrets(url)
            raise RuntimeError(
                f"External provider at {safe_url} is temporarily unavailable (circuit breaker OPEN). "
                f"Using safe local fallback."
            )

        req_headers = {"User-Agent": "Mozilla/5.0 (HELIOX-AI-Resilient/1.0)"}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, data=data, headers=req_headers)
        active_timeout = timeout or self.default_timeout
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=active_timeout) as resp:
                    payload = resp.read()
                    self.circuit_breaker.record_success()
                    return payload
            except Exception as exc:
                last_exc = exc
                safe_msg = redact_secrets(str(exc))
                if not self.is_transient_error(exc):
                    # Non-transient errors (e.g. 401 Unauthorized, 403 Forbidden, 404 Not Found)
                    # should fail immediately without wasting retries.
                    self.circuit_breaker.record_failure(exc)
                    logger.error("Non-transient HTTP error on attempt %d: %s", attempt, safe_msg)
                    raise RuntimeError(f"External API failure: {safe_msg}") from exc

                if attempt == self.max_retries:
                    self.circuit_breaker.record_failure(exc)
                    logger.warning("All %d HTTP retries exhausted for external API: %s", self.max_retries, safe_msg)
                    break

                retry_after = self.get_retry_after(exc)
                if retry_after is not None and 0 < retry_after <= 10.0:
                    delay = retry_after
                else:
                    # Exponential backoff with jitter
                    delay = self.backoff_factor * (2 ** (attempt - 1)) + random.uniform(0.05, 0.25)

                logger.info(
                    "Transient HTTP failure on attempt %d/%d (%s). Backing off for %.2fs",
                    attempt,
                    self.max_retries,
                    safe_msg,
                    delay,
                )
                time.sleep(delay)

        self.circuit_breaker.record_failure(last_exc or RuntimeError("Unknown HTTP failure"))
        raise RuntimeError(
            f"External API provider unavailable after {self.max_retries} attempts: {redact_secrets(str(last_exc))}"
        ) from last_exc
