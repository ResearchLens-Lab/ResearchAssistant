"""
Registry and factory for embedding models.
"""

import logging
from typing import Optional
from rag.config.settings import settings
from rag.embeddings.embedder import BaseEmbedder, DeterministicMockEmbedder, FastEmbedder, GeminiEmbedder

logger = logging.getLogger(__name__)


class EmbeddingModelRegistry:
    """
    Factory creating configured embedding provider instances.
    """

    @staticmethod
    def get_embedder(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        dimension: Optional[int] = None,
    ) -> BaseEmbedder:
        prov = (provider or settings.embedding_provider).lower()
        dim = dimension or settings.embedding_dimension

        if prov == "gemini":
            model = model_name or settings.embedding_model
            if model != "gemini-embedding-001":
                raise ValueError(f"Unsupported Gemini embedding model '{model}'.")
            return GeminiEmbedder(api_key=api_key or settings.gemini_api_key, model=model, dimension=dim)
        elif prov in {"fastembed", "local"}:
            model = model_name or settings.embedding_model
            if model != "BAAI/bge-small-en-v1.5":
                raise ValueError(f"Unsupported local embedding model '{model}'.")
            if dim != 384:
                raise ValueError("BAAI/bge-small-en-v1.5 requires EMBEDDING_DIMENSION=384.")
            return FastEmbedder(model=model, dimension=dim)
        elif prov == "mock":
            logger.info("Initializing DeterministicMockEmbedder (dim: %d)", dim)
            return DeterministicMockEmbedder(dimension=dim)
        else:
            raise ValueError(f"Unsupported embedding provider '{prov}'. Choose 'fastembed'/'local', 'gemini' or 'mock'.")
