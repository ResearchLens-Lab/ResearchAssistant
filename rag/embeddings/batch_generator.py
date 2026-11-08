"""
Batch embedding generator utility.
Handles batching, progress logging, and chunk embedding generation.
"""

import logging
from typing import List
from rag.embeddings.embedder import BaseEmbedder
from rag.chunking.metadata import DocumentChunk

logger = logging.getLogger(__name__)


class BatchEmbeddingGenerator:
    """
    Batches document chunks or raw texts for efficient embedding generation.
    """

    def __init__(self, embedder: BaseEmbedder, batch_size: int = 32):
        self.embedder = embedder
        self.batch_size = max(1, batch_size)

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[List[float]]:
        """
        Embeds a list of DocumentChunks in batches and returns vectors.
        """
        if not chunks:
            return []

        vectors: List[List[float]] = []
        for start_idx in range(0, len(chunks), self.batch_size):
            batch = chunks[start_idx:start_idx + self.batch_size]
            vectors.extend(self.embedder.embed_documents([chunk.text for chunk in batch]))
        return vectors

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds texts in batches.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        total = len(texts)

        for start_idx in range(0, total, self.batch_size):
            end_idx = min(start_idx + self.batch_size, total)
            batch = texts[start_idx:end_idx]

            logger.debug("Generating embeddings for batch %d-%d of %d", start_idx + 1, end_idx, total)
            batch_vectors = self.embedder.embed_documents(batch)
            if len(batch_vectors) != len(batch):
                raise RuntimeError(f"Embedding provider returned {len(batch_vectors)} vectors for {len(batch)} chunks.")
            all_embeddings.extend(batch_vectors)

        logger.info("Generated embeddings for %d items using %s", len(all_embeddings), self.embedder.__class__.__name__)
        return all_embeddings
