"""Application-level accounting for every real provider generation attempt."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from rag.config.settings import settings
from rag.generation.local_state import LLMUsageBudgetExceeded, SQLiteLLMState
from rag.generation.llm_client import BaseLLMClient
from rag.generation.provider_errors import LLMProviderError, classify_provider_error

_request_calls: ContextVar[list | None] = ContextVar("llm_request_calls", default=None)


class BudgetedLLMClient(BaseLLMClient):
    """Wraps generation and streaming so answer, repair and judge paths share one budget."""

    def __init__(self, client: BaseLLMClient, provider: str, state: SQLiteLLMState | None = None):
        self.client = client
        self.provider = provider
        self.state = state or SQLiteLLMState()
        self.supports_streaming = client.supports_streaming

    def _reserve(self):
        if self.provider == "mock":
            return
        if self.provider == "gemini" and not getattr(self.client, "api_key", None):
            raise LLMProviderError("missing_credentials", "Gemini generation is unavailable because GEMINI_API_KEY is not configured.")
        if self.provider == "openai" and not getattr(self.client, "api_key", None):
            raise LLMProviderError("missing_credentials", "Generation is unavailable because LLM_API_KEY is not configured.")
        self.state.reserve_call(self.provider, settings.llm_daily_call_budget)
        calls = _request_calls.get()
        if calls is not None:
            calls[0] += 1

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        self._reserve()
        try:
            return self.client.generate(system_prompt, user_prompt, temperature, max_tokens)
        except (LLMUsageBudgetExceeded, LLMProviderError):
            raise
        except Exception as exc:
            raise classify_provider_error(exc) from exc

    def generate_stream(self, system_prompt: str, user_prompt: str,
                        temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        self._reserve()
        try:
            yield from self.client.generate_stream(system_prompt, user_prompt, temperature, max_tokens)
        except (LLMUsageBudgetExceeded, LLMProviderError):
            raise
        except Exception as exc:
            raise classify_provider_error(exc) from exc


def start_call_tracking():
    calls = [0, []]
    return _request_calls.set(calls), calls


def stop_call_tracking(token):
    _request_calls.reset(token)


def record_provider_usage(provider: str, model: str, usage: dict):
    """Record SDK-reported token counts in the current request; never estimate silently."""
    calls = _request_calls.get()
    if calls is not None and usage:
        calls[1].append({"provider": provider, "model": model, "measured": usage})
