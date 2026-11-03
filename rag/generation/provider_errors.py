"""Safe, stable classifications for provider failures."""

from __future__ import annotations


class LLMProviderError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def classify_provider_error(exc: Exception) -> LLMProviderError:
    """Classify provider failures without returning raw SDK bodies or credentials."""
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    status = status or getattr(response, "status_code", None)
    detail = " ".join((str(getattr(exc, "message", "")), str(exc))).casefold()
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    if status == 429:
        if any(word in detail for word in ("quota", "billing", "daily limit", "resource_exhausted")):
            return LLMProviderError("quota_exhausted", "The provider reports that this model's quota is exhausted.")
        return LLMProviderError("rate_limited", "The provider is temporarily rate limiting generation.")
    if status in (401, 403):
        if any(word in detail for word in ("quota", "billing", "resource_exhausted")):
            return LLMProviderError("quota_exhausted", "The provider reports that this model's quota is exhausted.")
        return LLMProviderError("authentication", "The generation provider rejected its credentials or access.")
    if status == 404 or any(word in detail for word in ("model not found", "unknown model", "invalid model")):
        return LLMProviderError("invalid_model", "The configured generation model is unavailable or invalid.")
    if isinstance(exc, (TimeoutError, ConnectionError)) or "timeout" in type(exc).__name__.casefold():
        return LLMProviderError("transient", "The generation provider timed out.")
    if status and status >= 500:
        return LLMProviderError("transient", "The generation provider is temporarily unavailable.")
    return LLMProviderError("provider_error", "The generation provider could not complete this request.")
