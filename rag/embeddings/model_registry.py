"""
Registry and factory for embedding models.
"""

import logging
from typing import Optional
from rag.config.settings import settings
from rag.embeddings.embedder import BaseEmbedder, DeterministicMockEmbedder, OpenAIEmbedder

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

        if prov == "openai":
            key = api_key or settings.embedding_api_key or settings.llm_api_key
            model = model_name or (settings.embedding_model if settings.embedding_model.startswith("text-embedding") else "text-embedding-3-small")
            # OpenAI text-embedding-3-small default is 1536
            out_dim = dim
            expected_dim = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072,
                            "text-embedding-ada-002": 1536}.get(model)
            if expected_dim and out_dim != expected_dim:
                raise ValueError(f"Embedding model {model} requires dimension {expected_dim}; configured {out_dim}.")
            if model not in {"text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"}:
                raise ValueError(f"Unsupported OpenAI embedding model '{model}'.")
            if model == "text-embedding-ada-002" and out_dim != 1536:
                raise ValueError("text-embedding-ada-002 requires dimension 1536.")
            logger.info("Initializing OpenAIEmbedder (model: %s, dim: %d)", model, out_dim)
            return OpenAIEmbedder(api_key=key, model=model, dimension=out_dim)
        elif prov == "mock":
            logger.info("Initializing DeterministicMockEmbedder (dim: %d)", dim)
            return DeterministicMockEmbedder(dimension=dim)
        else:
            raise ValueError(f"Unsupported embedding provider '{prov}'. Choose 'mock' or 'openai'.")
