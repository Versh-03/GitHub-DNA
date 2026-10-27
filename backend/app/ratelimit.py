"""
Groq API rate-limit and quota-exhaustion parsing, backoff calculation, and error sanitization.
"""
import random
import re
from dataclasses import dataclass
from typing import Optional
from openai import RateLimitError

API_KEY_PATTERN = re.compile(r"gsk_[A-Za-z0-9_\-]{8,}")
RETRY_AFTER_PATTERN = re.compile(r"(?:try again in|retry after|resets in)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|seconds?)", re.IGNORECASE)
RETRY_AFTER_MS_PATTERN = re.compile(r"(?:try again in|retry after|resets in)\s*([0-9]+)\s*ms", re.IGNORECASE)


def sanitize_message(text: str) -> str:
    """Strip out potential API keys or sensitive authorization fragments from strings."""
    if not text:
        return ""
    # Strip Bearer tokens first
    cleaned = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]{8,}", "Bearer ***", str(text), flags=re.IGNORECASE)
    # Then strip any remaining gsk_ keys
    cleaned = API_KEY_PATTERN.sub("gsk_***", cleaned)
    return cleaned


class LLMRateLimitExceeded(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None, safe_detail: str = ""):
        super().__init__(sanitize_message(message))
        self.retry_after = retry_after
        self.safe_detail = sanitize_message(safe_detail or message)


class LLMQuotaExhausted(Exception):
    def __init__(self, message: str, safe_detail: str = ""):
        super().__init__(sanitize_message(message))
        self.safe_detail = sanitize_message(safe_detail or message)


@dataclass
class RateLimitInfo:
    is_quota_exhausted: bool
    retry_after: Optional[float]
    safe_detail: str
    error_code: Optional[str]
    error_type: Optional[str]


def parse_rate_limit_error(err: RateLimitError) -> RateLimitInfo:
    """
    Extracts headers, error code, quota exhaustion flags, and retry delay safely.
    """
    body = err.body if isinstance(err.body, dict) else {}
    error_dict = body.get("error", {}) if isinstance(body, dict) else {}

    raw_message = str(error_dict.get("message") or err.message or "")
    safe_detail = sanitize_message(raw_message)

    code = str(error_dict.get("code") or err.code or "").lower()
    err_type = str(error_dict.get("type") or "").lower()

    # 1. Detect quota exhaustion
    is_quota = False
    lower_msg = raw_message.lower()
    if code in ("insufficient_quota", "quota_exceeded") or err_type in ("insufficient_quota", "quota_exceeded"):
        is_quota = True
    elif "quota" in lower_msg and ("exceeded" in lower_msg or "billing" in lower_msg or "insufficient" in lower_msg):
        is_quota = True
    elif "credit" in lower_msg and ("expired" in lower_msg or "insufficient" in lower_msg):
        is_quota = True

    # 2. Extract retry delay from headers or message
    retry_after: Optional[float] = None

    # Check HTTP response headers if available
    headers = getattr(err.response, "headers", None)
    if headers:
        # Standard retry-after header
        h_retry = headers.get("retry-after")
        if h_retry:
            try:
                retry_after = float(h_retry.strip())
            except ValueError:
                pass

        if retry_after is None:
            h_ms = headers.get("retry-after-ms")
            if h_ms:
                try:
                    retry_after = float(h_ms.strip()) / 1000.0
                except ValueError:
                    pass

        if retry_after is None:
            # Groq custom headers: x-ratelimit-reset-tokens (e.g., '6s' or '350ms')
            for h_name in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
                h_val = headers.get(h_name)
                if h_val:
                    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*s?$", h_val.strip())
                    if m:
                        try:
                            retry_after = float(m.group(1))
                            break
                        except ValueError:
                            pass
                    m_ms = re.match(r"^([0-9]+)\s*ms$", h_val.strip())
                    if m_ms:
                        try:
                            retry_after = float(m_ms.group(1)) / 1000.0
                            break
                        except ValueError:
                            pass

    # If no header, parse retry delay from error message string
    if retry_after is None and raw_message:
        m = RETRY_AFTER_PATTERN.search(raw_message)
        if m:
            try:
                retry_after = float(m.group(1))
            except ValueError:
                pass
        else:
            m_ms = RETRY_AFTER_MS_PATTERN.search(raw_message)
            if m_ms:
                try:
                    retry_after = float(m_ms.group(1)) / 1000.0
                except ValueError:
                    pass

    return RateLimitInfo(
        is_quota_exhausted=is_quota,
        retry_after=retry_after,
        safe_detail=safe_detail,
        error_code=code or None,
        error_type=err_type or None,
    )


def calculate_backoff(attempt: int, base_delay: float = 2.0, max_delay: float = 8.0) -> float:
    """
    Computes bounded exponential backoff with random jitter.
    Attempt 1: ~2.1s - 2.8s
    Attempt 2: ~4.1s - 4.8s
    """
    exp = base_delay * (2 ** (attempt - 1))
    jitter = random.uniform(0.1, 0.9)
    return min(exp + jitter, max_delay)
