"""
Ingestion Pipeline for ResearchLens RAG.
Orchestrates: File -> Load -> Normalize -> Chunk -> Batch Embed -> ChromaDB Index.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from rag.ingestion.document_loader import DocumentLoaderFactory, BaseDocumentLoader, TextDocumentLoader
from rag.ingestion.document_normalizer import NormalizedDocument
from rag.chunking.chunker import DocumentChunker
from rag.embeddings.embedder import BaseEmbedder
from rag.embeddings.model_registry import EmbeddingModelRegistry
from rag.embeddings.batch_generator import BatchEmbeddingGenerator
from rag.vectorstore.vector_repository import VectorRepository

logger = logging.getLogger(__name__)


class IngestResult(BaseModel):
    """
    Standard result returned after document ingestion.
    """
    success: bool
    status: str = Field(..., description="'indexed' or 'failed'")
    document_id: str
    paper_id: str
    chunk_count: int = 0
    total_pages: int = 0
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionPipeline:
    """
    End-to-end ingestion pipeline for indexing research documents into ChromaDB.
    """

    def __init__(
        self,
        chunker: Optional[DocumentChunker] = None,
        embedder: Optional[BaseEmbedder] = None,
        vector_repo: Optional[VectorRepository] = None,
    ):
        self.chunker = chunker or DocumentChunker()
        self.embedder = embedder or EmbeddingModelRegistry.get_embedder()
        self.vector_repo = vector_repo or VectorRepository()
        self.batch_generator = BatchEmbeddingGenerator(self.embedder)

    def ingest_file(
        self,
        file_path: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestResult:
        """
        Loads a document file (PDF, TXT, MD), processes, chunks, embeds, and indexes it.
        """
        start_time = time.time()
        meta = metadata.copy() if metadata else {}
        if paper_id:
            meta["paper_id"] = paper_id

        try:
            loader: BaseDocumentLoader = DocumentLoaderFactory.get_loader(file_path)
            normalized_doc: NormalizedDocument = loader.load(file_path, metadata=meta)

            result = self._process_normalized_doc(normalized_doc, start_time)
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("Ingestion failed for file '%s': %s", file_path, e, exc_info=True)
            doc_id = meta.get("document_id", "unknown_doc")
            pid = meta.get("paper_id", paper_id or "unknown_paper")
            return IngestResult(
                success=False,
                status="failed",
                document_id=doc_id,
                paper_id=pid,
                chunk_count=0,
                total_pages=0,
                error=str(e),
                execution_time_seconds=round(elapsed, 3),
            )

    def ingest_text(
        self,
        content: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestResult:
        """
        Directly ingests a raw string or markdown text.
        """
        start_time = time.time()
        meta = metadata.copy() if metadata else {}
        if paper_id:
            meta["paper_id"] = paper_id

        try:
            loader = TextDocumentLoader()
            normalized_doc: NormalizedDocument = loader.load_text(content=content, metadata=meta)
            return self._process_normalized_doc(normalized_doc, start_time)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("Ingestion failed for raw text: %s", e, exc_info=True)
            return IngestResult(
                success=False,
                status="failed",
                document_id=meta.get("document_id", "unknown_doc"),
                paper_id=meta.get("paper_id", paper_id or "unknown_paper"),
                chunk_count=0,
                total_pages=0,
                error=str(e),
                execution_time_seconds=round(elapsed, 3),
            )

    def _process_normalized_doc(
        self,
        doc: NormalizedDocument,
        start_time: float,
    ) -> IngestResult:
        # 1. Chunk document
        chunks = self.chunker.chunk_document(doc)
        if not chunks:
            elapsed = time.time() - start_time
            return IngestResult(
                success=False,
                status="failed",
                document_id=doc.document_id,
                paper_id=doc.paper_id,
                chunk_count=0,
                total_pages=doc.total_pages,
                error="No text chunks could be extracted from the document.",
                execution_time_seconds=round(elapsed, 3),
            )

        # 2. Generate embeddings in batches
        embeddings = self.batch_generator.embed_chunks(chunks)

        # 3. Upsert into ChromaDB
        upserted_count = self.vector_repo.upsert_chunks(chunks, embeddings)

        elapsed = time.time() - start_time
        logger.info(
            "Ingestion successful for paper_id='%s' (doc_id='%s'): %d chunks indexed in %.2fs",
            doc.paper_id,
            doc.document_id,
            upserted_count,
            elapsed,
        )

        return IngestResult(
            success=True,
            status="indexed",
            document_id=doc.document_id,
            paper_id=doc.paper_id,
            chunk_count=upserted_count,
            total_pages=doc.total_pages,
            execution_time_seconds=round(elapsed, 3),
            metadata={
                "title": doc.title,
                "authors": doc.authors,
                "year": doc.year,
                "sections": [s.name for s in doc.sections],
            },
        )

    def delete_paper(self, paper_id: str) -> int:
        """
        Deletes indexed chunks for a paper.
        """
        return self.vector_repo.delete_paper_chunks(paper_id)
