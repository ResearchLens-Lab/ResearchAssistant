"""
Embedding generation interfaces and provider implementations.
Includes DeterministicMockEmbedder (for offline local development & fast CI)
and OpenAIEmbedder (as the standard real cloud embedding provider).
"""

import math
import hashlib
import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import httpx

from rag.config.settings import settings
from rag.embeddings.cache import SQLiteEmbeddingCache

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


class FastEmbedder(BaseEmbedder):
    """CPU-local ONNX embeddings with a persistent hash-keyed vector cache."""

    _models: dict[tuple[str, str], object] = {}
    _models_lock = threading.RLock()

    def __init__(self, model: Optional[str] = None, dimension: int = 384,
                 cache: Optional[SQLiteEmbeddingCache] = None):
        try:
            import fastembed
        except ImportError as exc:
            raise RuntimeError("Local embeddings require fastembed. Install the project requirements.") from exc
        self.model = model or settings.embedding_model
        self._dimension = dimension
        self.model_version = f"fastembed-{fastembed.__version__}:{self.model}"
        cache_path = settings.embedding_cache_path or str(Path(settings.chroma_persist_dir) / "embedding_cache.sqlite3")
        self.cache = cache or SQLiteEmbeddingCache(cache_path)
        self._cache_dir = str(Path(settings.fastembed_cache_dir).resolve())
        self._inference_lock = threading.RLock()
        self._tokenizer = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_model(self):
        key = (self.model_version, self._cache_dir)
        with self._models_lock:
            if key not in self._models:
                from fastembed import TextEmbedding
                threads = max(1, min(4, os.cpu_count() or 4))
                self._models[key] = TextEmbedding(model_name=self.model, cache_dir=self._cache_dir, threads=threads)
            return self._models[key]

    def split_text_for_embedding(self, text: str, max_tokens: int = 512, overlap_tokens: int = 80) -> list[tuple[str, int]]:
        """Split text at this model's real tokenizer boundaries without truncation.

        FastEmbed configures the BGE tokenizer to truncate embedding inputs at
        512 tokens. Chunking by words alone cannot guarantee that limit (some
        words expand to several subword tokens), so the local pipeline uses an
        independent, untruncated tokenizer to split oversized chunks first.
        Returned text slices overlap and retain every non-whitespace source
        character across adjacent chunks.
        """
        if not text.strip():
            return []
        with self._inference_lock:
            if self._tokenizer is None:
                try:
                    from tokenizers import Tokenizer
                except ImportError as exc:
                    raise RuntimeError("FastEmbed token-aware chunking requires the tokenizers package.") from exc
                model = self._get_model()
                model.model._ensure_tokenizer()
                self._tokenizer = Tokenizer.from_str(model.model.tokenizer.to_str())
                self._tokenizer.no_truncation()
            encoding = self._tokenizer.encode(text)

        token_offsets = [(start, end) for start, end in encoding.offsets if end > start]
        special_tokens = len(encoding.ids) - len(token_offsets)
        token_limit = max_tokens - special_tokens
        if token_limit < 1:
            raise ValueError("Embedding token limit is too small for the model's special tokens.")
        if len(encoding.ids) <= max_tokens:
            return [(text, len(encoding.ids))]

        overlap = min(max(0, overlap_tokens), token_limit - 1)
        parts: list[tuple[str, int]] = []
        first_token = 0
        total_tokens = len(token_offsets)
        while first_token < total_tokens:
            end_token = min(first_token + token_limit, total_tokens)
            char_start = 0 if first_token == 0 else token_offsets[first_token][0]
            char_end = len(text) if end_token == total_tokens else token_offsets[end_token - 1][1]
            part = text[char_start:char_end].strip()
            if not part:
                first_token += 1
                continue
            part_tokens = len(self._tokenizer.encode(part).ids)
            if part_tokens > max_tokens:
                excess = part_tokens - max_tokens
                end_token = max(first_token + 1, end_token - excess)
                char_end = token_offsets[end_token - 1][1]
                part = text[char_start:char_end].strip()
                part_tokens = len(self._tokenizer.encode(part).ids)
            parts.append((part, part_tokens))
            if end_token == total_tokens:
                break
            first_token = max(first_token + 1, end_token - overlap)
        return parts

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        hashes = [self.cache.content_hash(text) for text in texts]
        cached = self.cache.get_many(self.model_version, texts)
        result: list[Optional[list[float]]] = [cached.get(key) for key in hashes]
        indexes_by_hash: dict[str, list[int]] = {}
        missing_by_hash: dict[str, tuple[int, str]] = {}
        for index, (key, text) in enumerate(zip(hashes, texts)):
            indexes_by_hash.setdefault(key, []).append(index)
            if result[index] is None:
                missing_by_hash.setdefault(key, (index, text))
        missing = list(missing_by_hash.items())
        if missing:
            batch_size = max(1, min(settings.embedding_batch_size, 128))
            with self._inference_lock:
                # A single local ONNX model is already configured with one
                # intra-op thread. FastEmbed interprets parallel=1 as a request
                # for a multiprocessing worker pool, which uses spawn on
                # Windows and can fail when called from an API worker or an
                # interactive process. None keeps inference in this process.
                generated = self._get_model().embed([text for _, (_, text) in missing], batch_size=batch_size, parallel=None)
                vectors = [vector.tolist() for vector in generated]
            if len(vectors) != len(missing):
                raise RuntimeError(f"FastEmbed returned {len(vectors)} vectors for {len(missing)} texts.")
            cache_items = []
            for (key, (index, text)), vector in zip(missing, vectors):
                if len(vector) != self.dimension:
                    raise RuntimeError(f"FastEmbed returned vector dimension {len(vector)}; expected {self.dimension}.")
                for target_index in indexes_by_hash[key]:
                    result[target_index] = vector
                cache_items.append((text, vector))
            self.cache.put_many(self.model_version, cache_items)
        return [vector for vector in result if vector is not None]

    def embed_query(self, text: str) -> List[float]:
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else [0.0] * self.dimension


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


class GeminiEmbedder(BaseEmbedder):
    """Gemini embeddings through Google's official google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 dimension: int = 768, client=None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.embedding_model
        self._dimension = dimension
        if not 128 <= dimension <= 3072:
            raise ValueError("Gemini embedding dimension must be between 128 and 3072.")
        self.client = client

    def _get_client(self):
        if self.client is None:
            if not self.api_key:
                raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY.")
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Gemini support requires the google-genai package.") from exc
            self.client = genai.Client(api_key=self.api_key)
        return self.client

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        from google.genai import types
        try:
            result = self._get_client().models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dimension,
                ),
            )
            vectors = [item.values for item in result.embeddings]
            if len(vectors) != len(texts) or any(len(vector) != self.dimension for vector in vectors):
                raise RuntimeError("Gemini returned an unexpected embedding count or dimension.")
            return vectors
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            if isinstance(exc, ValueError) and "GEMINI_API_KEY" in str(exc):
                raise
            code = getattr(exc, "code", None)
            detail = str(getattr(exc, "message", "") or exc).replace(self.api_key or "\0", "[redacted]")
            detail = " ".join(detail.split())[:400]
            if code == 429:
                message = f"Gemini embedding quota or rate limit reached (HTTP 429): {detail}. Check Gemini API quota, then retry."
            elif code in (400, 404):
                message = f"Gemini rejected the embedding configuration (HTTP {code}): {detail}. Check EMBEDDING_MODEL and dimension."
            else:
                suffix = f" (HTTP {code})" if code else ""
                message = f"Gemini embedding request failed{suffix} ({type(exc).__name__}): {detail}"
            raise RuntimeError(message) from exc

    def embed_query(self, text: str) -> List[float]:
        from google.genai import types
        try:
            result = self._get_client().models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=self.dimension,
                ),
            )
            vector = result.embeddings[0].values
            if len(vector) != self.dimension:
                raise RuntimeError("Gemini returned an unexpected embedding dimension.")
            return vector
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            if isinstance(exc, ValueError) and "GEMINI_API_KEY" in str(exc):
                raise
            code = getattr(exc, "code", None)
            detail = str(getattr(exc, "message", "") or exc).replace(self.api_key or "\0", "[redacted]")
            detail = " ".join(detail.split())[:400]
            suffix = f" (HTTP {code})" if code else ""
            raise RuntimeError(f"Gemini query embedding failed{suffix} ({type(exc).__name__}): {detail}") from exc
