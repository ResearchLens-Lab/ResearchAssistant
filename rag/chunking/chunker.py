"""
Main document chunker orchestrator.
Manages chunking strategy execution and metadata integrity checks.
"""

import logging
import threading
from typing import Callable, List, Optional
from rag.ingestion.document_normalizer import NormalizedDocument
from rag.chunking.metadata import DocumentChunk, make_chunk_id
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
        token_limiter: Optional[Callable[[str], list[tuple[str, int]]]] = None,
    ):
        c_size = chunk_size or settings.chunk_size
        c_overlap = chunk_overlap or settings.chunk_overlap
        self.strategy = strategy or SectionAwareChunkingStrategy(
            chunk_size=c_size,
            chunk_overlap=c_overlap,
        )
        self._chunk_lock = threading.Lock()
        self.token_limiter = token_limiter

    def chunk_document(self, document: NormalizedDocument) -> List[DocumentChunk]:
        """
        Chunks the document and verifies non-empty output and provenance integrity.
        """
        with self._chunk_lock:
            if not document.pages and not document.sections:
                logger.warning("Attempted to chunk an empty document: %s", document.document_id)
                return []

            try:
                chunks = self.strategy.chunk(document)
                if self.token_limiter:
                    chunks = self._limit_embedding_tokens(chunks, document)
                logger.info(
                    "Document [%s] (paper: %s) chunked into %d chunks",
                    document.document_id,
                    document.paper_id,
                    len(chunks),
                )
                return chunks
            finally:
                clear_cache = getattr(self.strategy, "clear_match_cache", None)
                if callable(clear_cache):
                    clear_cache()

    def _limit_embedding_tokens(self, chunks: List[DocumentChunk], document: NormalizedDocument) -> List[DocumentChunk]:
        """Apply the configured embedder's tokenizer limit without dropping text."""
        from rag.chunking.metadata import DocumentChunk as Chunk

        expanded: List[DocumentChunk] = []
        page_offsets = None
        source_text = document.full_text
        if isinstance(self.strategy, SectionAwareChunkingStrategy):
            page_offsets = self.strategy._build_page_index(document.pages)
            self.strategy._match_cursor = 0

        for chunk in chunks:
            parts = self.token_limiter(chunk.text)
            if len(parts) == 1 and parts[0][0] == chunk.text:
                index = len(expanded)
                meta = chunk.metadata.model_copy(update={
                    "chunk_index": index,
                    "token_count": parts[0][1],
                })
                is_pdf = (document.metadata.source_format or "pdf").lower() == "pdf"
                meta.chunk_id = make_chunk_id(document.paper_id, document.document_id, index,
                                              meta.page_start, meta.page_end, is_pdf)
                if isinstance(self.strategy, SectionAwareChunkingStrategy):
                    meta.locator = self.strategy._locator_for(document, chunk.text, meta.section, index + 1)
                expanded.append(Chunk(text=chunk.text, metadata=meta))
                continue

            for text, token_count in parts:
                index = len(expanded)
                page_start = chunk.metadata.page_start
                page_end = chunk.metadata.page_end
                if page_offsets is not None:
                    page_start, page_end = self.strategy._find_page_range_for_text(
                        document_text=source_text,
                        chunk_text=text,
                        page_offsets=page_offsets,
                        fallback_start=page_start or 1,
                        fallback_end=page_end or page_start or 1,
                    )
                meta = chunk.metadata.model_copy(update={
                    "chunk_index": index,
                    "token_count": token_count,
                    "page_start": page_start,
                    "page_end": page_end,
                })
                is_pdf = (document.metadata.source_format or "pdf").lower() == "pdf"
                meta.chunk_id = make_chunk_id(document.paper_id, document.document_id, index,
                                              page_start, page_end, is_pdf)
                if isinstance(self.strategy, SectionAwareChunkingStrategy):
                    meta.locator = self.strategy._locator_for(document, text, meta.section, index + 1)
                expanded.append(Chunk(text=text, metadata=meta))
        return expanded
