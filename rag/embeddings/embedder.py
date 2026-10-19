"""
Embedding generation interfaces and provider implementations.
Includes DeterministicMockEmbedder (for offline local development & fast CI)
and OpenAIEmbedder (as the standard real cloud embedding provider).
"""

import math
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
import httpx

from rag.config.settings import settings

logger = logging.getLogger(__name__)


class BaseEmbedder(ABC):
    """
    Abstract Base Class for text embedding generation.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a list of document chunk texts."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embeds a single user query."""
        pass


class DeterministicMockEmbedder(BaseEmbedder):
    """
    Fast, deterministic dense vector generator for local testing and CI without external API dependencies.
    Uses token-hashed feature projection with L2 normalization to ensure non-zero cosine similarity
    for overlapping vocabulary and keyword semantics.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed_single(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self._dimension

        vec = [0.0] * self._dimension
        tokens = text.lower().split()

        for token in tokens:
            # Clean token
            clean = "".join(c for c in token if c.isalnum())
            if not clean:
                continue
            # Hash to index and sign
            h = int(hashlib.md5(clean.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
            vec[idx] += sign

            # Also hash character n-grams for subword matching
            if len(clean) >= 4:
                for i in range(len(clean) - 3):
                    ngram = clean[i:i+4]
                    nh = int(hashlib.sha256(ngram.encode("utf-8")).hexdigest(), 16)
                    n_idx = nh % self._dimension
                    n_sign = 1.0 if ((nh >> 8) & 1) == 0 else -1.0
                    vec[n_idx] += 0.5 * n_sign

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [x / norm for x in vec]
        return [0.0] * self._dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_single(text)


class OpenAIEmbedder(BaseEmbedder):
    """
    OpenAI text embedding provider via HTTP API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = 1536,
    ):
        self.api_key = api_key or settings.embedding_api_key
        self.model = model or "text-embedding-3-small"
        self._dimension = dimension
        if not self.api_key:
            logger.warning("OpenAIEmbedder initialized without API key. Calls will fail unless key is provided.")

    @property
    def dimension(self) -> int:
        return self._dimension

    def _call_api(self, input_texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise ValueError("OpenAI API key is missing. Set EMBEDDING_API_KEY or LLM_API_KEY.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": input_texts,
            "model": self.model,
        }
        if self.model in {"text-embedding-3-small", "text-embedding-3-large"}:
            payload["dimensions"] = self.dimension

        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
                resp = client.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                vectors = [item["embedding"] for item in sorted_data]
                if any(len(vector) != self.dimension for vector in vectors):
                    raise RuntimeError(f"Embedding provider returned an unexpected vector dimension; expected {self.dimension}.")
                return vectors
        except httpx.TimeoutException as exc:
            raise RuntimeError("Embedding provider request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Embedding provider rejected the request (HTTP {exc.response.status_code}).") from exc

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._call_api(texts)

    def embed_query(self, text: str) -> List[float]:
        results = self._call_api([text])
        return results[0] if results else [0.0] * self._dimension
