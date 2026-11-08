"""
LLM client interfaces and implementations.
Includes MockGroundedLLMClient for deterministic local testing/CI
and OpenAILLMClient as the standard real LLM provider.
"""

import re
import logging
import atexit
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import httpx

from rag.config.settings import settings
from rag.generation.provider_errors import classify_provider_error
from rag.generation.provider_errors import LLMProviderError

logger = logging.getLogger(__name__)

# One pooled HTTP connection manager is reused across local model requests.
_OLLAMA_HTTP = httpx.Client()
_OLLAMA_REQUEST_SLOT = threading.BoundedSemaphore(1)
atexit.register(_OLLAMA_HTTP.close)


class BaseLLMClient(ABC):
    """
    Abstract LLM client interface.
    """
    supports_streaming = False

    def generate_stream(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        """Fallback for providers without incremental generation."""
        yield self.generate(system_prompt, user_prompt, temperature, max_tokens)

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generates text completion for given system and user prompts.
        """
        pass


class MockGroundedLLMClient(BaseLLMClient):
    """
    Deterministic, offline LLM simulator designed for testing and offline local development.
    Extracts facts directly from supplied evidence blocks and synthesizes grounded answers
    with valid inline citations [S1], [S2].
    """

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        # Check if context has no evidence
        if "[NO RELEVANT EVIDENCE FOUND" in user_prompt:
            return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Parse source blocks from user prompt: e.g. [S1] (Paper: paper_1, ...) \n text
        source_matches = re.findall(
            r"\[(S\d+)\]\s*\(([^)]+)\)\n(.*?)(?=\n\n---\n\n|\Z|\nQUESTION:|\nFOCUS AREA)",
            user_prompt,
            flags=re.DOTALL,
        )

        if not source_matches:
            # Check if any inline sources exist
            raw_sources = re.findall(r"\[(S\d+)\]", user_prompt)
            if not raw_sources:
                return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Check task type
        is_summary = "summarize" in system_prompt.lower() or "summary" in user_prompt.lower()
        is_comparison = "compare" in system_prompt.lower() or "comparison" in user_prompt.lower()

        if is_summary:
            return self._generate_mock_summary(source_matches)
        elif is_comparison:
            return self._generate_mock_comparison(source_matches, user_prompt)
        else:
            return self._generate_mock_qa(source_matches, user_prompt)

    def _generate_mock_summary(self, source_matches: List[tuple]) -> str:
        if not source_matches:
            return "The available passages do not provide enough evidence for a summary."
        evidence = "\n\n".join(
            f"#### {header.strip()}\n\n{text.replace('<untrusted_source_evidence>', '').replace('</untrusted_source_evidence>', '').strip()} [{tag}]" for tag, header, text in source_matches if text.strip()
        )
        return ("### Overview\nNot reported in the retrieved passages.\n\n"
                "### Methodology\nNot reported in the retrieved passages.\n\n"
                "### Results\nNot reported in the retrieved passages.\n\n"
                "### Retrieved evidence\n" + evidence)

    def _generate_mock_comparison(self, source_matches: List[tuple], user_prompt: str) -> str:
        if not source_matches:
            return "The selected sources provide insufficient evidence for comparison."
        return "### Comparison: evidence from selected papers\n\n" + "\n\n".join(
            f"#### {header.strip()}\n\n{text.replace('<untrusted_source_evidence>', '').replace('</untrusted_source_evidence>', '').strip()} [{tag}]" for tag, header, text in source_matches if text.strip()
        )

    def _generate_mock_qa(self, source_matches: List[tuple], user_prompt: str) -> str:
        # Extract question
        q_match = re.search(r"QUESTION:\s*(.*)", user_prompt, re.DOTALL)
        question = q_match.group(1).strip() if q_match else "the query"

        if not source_matches:
            return "Based on the provided papers, there is insufficient evidence to answer this question."

        # Offline mode is explicitly extractive and makes no claims beyond the evidence.
        sections = ["The following retrieved passages are relevant. This offline response presents evidence without semantic synthesis:"]
        for tag, header, text in source_matches:
            passage = text.replace("<untrusted_source_evidence>", "").replace("</untrusted_source_evidence>", "").strip()
            if passage:
                sections.append(f"### {header.strip()}\n\n{passage} [{tag}]")
        return "\n\n".join(sections)


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI Chat Completion API Client.
    """
    supports_streaming = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or (settings.llm_model if "gpt" in getattr(settings, "llm_model", "") else "gpt-4o-mini")
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout_seconds

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set LLM_API_KEY in environment or .env.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data.get("usage"), dict):
                    from rag.generation.budgeted_client import record_provider_usage
                    record_provider_usage("openai", self.model, data["usage"])
                return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            raise RuntimeError("Language model request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Language model provider rejected the request (HTTP {exc.response.status_code}).") from exc

    def generate_stream(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set LLM_API_KEY in environment or .env.")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": [{"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}], "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens, "stream": True,
            "stream_options": {"include_usage": True}}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = httpx.Response(200, content=data).json()
                            if isinstance(chunk.get("usage"), dict):
                                from rag.generation.budgeted_client import record_provider_usage
                                record_provider_usage("openai", self.model, chunk["usage"])
                            delta = chunk["choices"][0].get("delta", {}).get("content") if chunk.get("choices") else None
                        except (ValueError, KeyError, IndexError, TypeError):
                            continue
                        if delta:
                            yield delta
        except httpx.TimeoutException as exc:
            raise RuntimeError("Language model request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Language model provider rejected the request (HTTP {exc.response.status_code}).") from exc


class GeminiLLMClient(BaseLLMClient):
    """Gemini text generation through Google's official google-genai SDK."""
    supports_streaming = True

    def __init__(self, api_key=None, model=None, temperature=None, max_tokens=None, timeout=None, client=None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or (settings.llm_model if "gemini" in getattr(settings, "llm_model", "") else "gemini-3.8-flash")
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout_seconds
        self.client = client

    def _get_client(self):
        if self.client is None:
            if not self.api_key:
                raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY.")
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Gemini support requires the google-genai package.") from exc
            # The SDK otherwise retries 429 and transient responses by default. One
            # SDK attempt keeps our application-level budget truthful.
            from google.genai import types
            self.client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(
                timeout=int(self.timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ))
        return self.client

    def _config(self, system_prompt, temperature, max_tokens):
        from google.genai import types
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.temperature if temperature is None else temperature,
            max_output_tokens=max_tokens or self.max_tokens,
        )

    def generate(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        try:
            response = self._get_client().models.generate_content(
                model=self.model, contents=user_prompt,
                config=self._config(system_prompt, temperature, max_tokens),
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty response.")
            usage = getattr(response, "usage_metadata", None)
            if usage:
                from rag.generation.budgeted_client import record_provider_usage
                counts = {key: getattr(usage, key, None) for key in
                          ("prompt_token_count", "candidates_token_count", "total_token_count")}
                record_provider_usage("gemini", self.model, {key: value for key, value in counts.items() if value is not None})
            return response.text
        except Exception as exc:
            if isinstance(exc, (RuntimeError, ValueError)) and "GEMINI_API_KEY" in str(exc):
                raise
            raise classify_provider_error(exc) from exc

    def generate_stream(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        try:
            response = self._get_client().models.generate_content_stream(
                model=self.model, contents=user_prompt,
                config=self._config(system_prompt, temperature, max_tokens),
            )
            for part in response:
                if part.text:
                    yield part.text
                usage = getattr(part, "usage_metadata", None)
                if usage:
                    from rag.generation.budgeted_client import record_provider_usage
                    counts = {key: getattr(usage, key, None) for key in
                              ("prompt_token_count", "candidates_token_count", "total_token_count")}
                    record_provider_usage("gemini", self.model, {key: value for key, value in counts.items() if value is not None})
        except Exception as exc:
            if isinstance(exc, ValueError) and "GEMINI_API_KEY" in str(exc):
                raise
            raise classify_provider_error(exc) from exc


class OllamaLLMClient(BaseLLMClient):
    """
    Local generation provider via Ollama's HTTP API (http://localhost:11434).
    Uses strict source grounding with zero external network access and zero paid APIs.
    """
    # Qwen thinking is never streamed to the UI; complete responses are verified
    # before they are returned to the application.
    supports_streaming = False

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or getattr(settings, "ollama_base_url", "http://localhost:11434")).rstrip("/")
        self.model = model or getattr(settings, "ollama_model", "qwen3.5:0.8b")
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.timeout = timeout or settings.llm_timeout_seconds

    def is_available(self) -> bool:
        """Fast non-blocking check whether Ollama is responsive."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": 4096,
            },
            "think": False,
            "keep_alive": "10m",
            "stream": False,
        }
        try:
            with _OLLAMA_REQUEST_SLOT:
                resp = _OLLAMA_HTTP.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
                if resp.status_code == 404:
                    raise LLMProviderError("model_not_installed", f"Ollama model '{self.model}' is not installed. Run 'ollama pull {self.model}'.")
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    raise LLMProviderError("empty_response", "Ollama returned an empty response.")
                return content
        except httpx.ConnectError as exc:
            raise LLMProviderError("provider_unavailable", f"Ollama is not running at {self.base_url}.") from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError("timeout", f"Ollama request timed out after {self.timeout}s.") from exc
        except Exception as exc:
            if isinstance(exc, LLMProviderError):
                raise
            raise LLMProviderError("transient", f"Ollama error: {exc}") from exc

    def generate_stream(self, system_prompt, user_prompt, temperature=None, max_tokens=None):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": 4096,
            },
            "think": False,
            "keep_alive": "10m",
            "stream": True,
        }
        try:
            with _OLLAMA_REQUEST_SLOT:
                with _OLLAMA_HTTP.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=self.timeout) as response:
                    if response.status_code == 404:
                        raise LLMProviderError("model_not_installed", f"Ollama model '{self.model}' is not installed.")
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = httpx.Response(200, content=line).json()
                            delta = chunk.get("message", {}).get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue
        except httpx.ConnectError as exc:
            raise LLMProviderError("provider_unavailable", f"Ollama is not running at {self.base_url}.") from exc
        except httpx.TimeoutException as exc:
            raise LLMProviderError("timeout", f"Ollama request timed out after {self.timeout}s.") from exc
        except Exception as exc:
            if isinstance(exc, LLMProviderError):
                raise
            raise LLMProviderError("transient", f"Ollama stream error: {exc}") from exc


class LLMClientFactory:
    """
    Factory creating configured LLM client.
    """

    @staticmethod
    def get_client(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        prov = (provider or settings.llm_provider).lower()
        if prov == "gemini":
            model = model_name or settings.llm_model
            if not model.startswith("gemini-"):
                raise LLMProviderError("invalid_model", "The configured generation model is not a supported Gemini model ID.")
            return GeminiLLMClient(api_key=api_key or settings.gemini_api_key, model=model)
        elif prov == "openai":
            key = api_key or settings.llm_api_key
            model = model_name or settings.llm_model
            logger.info("Initializing OpenAILLMClient (model: %s)", model)
            return OpenAILLMClient(api_key=key, model=model)
        elif prov in ("ollama", "qwen", "local_qwen"):
            base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
            model = model_name or getattr(settings, "ollama_model", "qwen3.5:0.8b")
            logger.info("Initializing OllamaLLMClient (model: %s, url: %s)", model, base_url)
            return OllamaLLMClient(base_url=base_url, model=model)
        elif prov == "mock":
            if settings.app_env != "testing":
                raise ValueError("The mock generation provider is only available when APP_ENV=testing.")
            logger.info("Initializing MockGroundedLLMClient")
            return MockGroundedLLMClient()
        else:
            raise ValueError(f"Unsupported LLM provider '{prov}'. Choose 'gemini', 'ollama', or 'mock'.")
