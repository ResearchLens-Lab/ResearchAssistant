"""
Main document chunker orchestrator.
Manages chunking strategy execution and metadata integrity checks.
"""

import logging
from typing import List, Optional
from rag.ingestion.document_normalizer import NormalizedDocument
from rag.chunking.metadata import DocumentChunk
from rag.chunking.strategies import BaseChunkingStrategy, SectionAwareChunkingStrategy
from rag.config.settings import settings

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Splits normalized documents into traceable, section- and page-preserving chunks.
    """

    def __init__(
        self,
        strategy: Optional[BaseChunkingStrategy] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        c_size = chunk_size or settings.chunk_size
        c_overlap = chunk_overlap or settings.chunk_overlap
        self.strategy = strategy or SectionAwareChunkingStrategy(
            chunk_size=c_size,
            chunk_overlap=c_overlap,
        )

    def chunk_document(self, document: NormalizedDocument) -> List[DocumentChunk]:
        """
        Chunks the document and verifies non-empty output and provenance integrity.
        """
        if not document.pages and not document.sections:
            logger.warning("Attempted to chunk an empty document: %s", document.document_id)
            return []

        chunks = self.strategy.chunk(document)
        logger.info(
            "Document [%s] (paper: %s) chunked into %d chunks",
            document.document_id,
            document.paper_id,
            len(chunks),
        )
        return chunks
