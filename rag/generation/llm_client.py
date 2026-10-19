"""
LLM client interfaces and implementations.
Includes MockGroundedLLMClient for deterministic local testing/CI
and OpenAILLMClient as the standard real LLM provider.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import httpx

from rag.config.settings import settings

logger = logging.getLogger(__name__)


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
        self.model = model or settings.llm_model
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
            "max_tokens": max_tokens or self.max_tokens, "stream": True}
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
                            delta = httpx.Response(200, content=data).json()["choices"][0].get("delta", {}).get("content")
                        except (ValueError, KeyError, IndexError, TypeError):
                            continue
                        if delta:
                            yield delta
        except httpx.TimeoutException as exc:
            raise RuntimeError("Language model request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Language model provider rejected the request (HTTP {exc.response.status_code}).") from exc


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
        if prov == "openai":
            key = api_key or settings.llm_api_key
            model = model_name or settings.llm_model
            logger.info("Initializing OpenAILLMClient (model: %s)", model)
            return OpenAILLMClient(api_key=key, model=model)
        elif prov == "mock":
            logger.info("Initializing MockGroundedLLMClient")
            return MockGroundedLLMClient()
        else:
            raise ValueError(f"Unsupported LLM provider '{prov}'. Choose 'mock' or 'openai'.")
