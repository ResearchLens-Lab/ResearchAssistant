"""
RAG Integration Client for FastAPI Backend.
Owned boundary contract between Abhay's Backend and Gorav's RAG Engine.
FastAPI route handlers should import and call this client without importing
internal RAG details directly.
"""

import logging
from typing import List, Optional, Dict, Any

from rag.pipelines.ingest_pipeline import IngestionPipeline, IngestResult
from rag.pipelines.query_pipeline import QueryPipeline
from rag.retrieval.query import QueryFilters
from rag.citations.citation_formatter import RAGResult
from rag.vectorstore.vector_repository import VectorRepository

logger = logging.getLogger(__name__)


class RAGClient:
    """
    High-level integration wrapper for the FastAPI backend service.
    Exposes clean synchronous and data-dictionary interfaces matching the API contract.
    """

    def __init__(
        self,
        ingest_pipeline: Optional[IngestionPipeline] = None,
        query_pipeline: Optional[QueryPipeline] = None,
        vector_repo: Optional[VectorRepository] = None,
    ):
        self._ingest_pipeline = ingest_pipeline or IngestionPipeline()
        self._query_pipeline = query_pipeline or QueryPipeline()
        self._vector_repo = vector_repo or VectorRepository()

    def ingest_document(
        self,
        file_path: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ingests a document file into the RAG vector store.

        Returns:
            dict: {
                "success": bool,
                "status": "indexed" | "failed",
                "document_id": str,
                "paper_id": str,
                "chunk_count": int,
                "total_pages": int,
                "error": str | None
            }
        """
        result: IngestResult = self._ingest_pipeline.ingest_file(
            file_path=file_path,
            paper_id=paper_id,
            metadata=metadata,
        )
        return result.model_dump()

    def ingest_text_content(
        self,
        content: str,
        paper_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ingests raw text or markdown research paper content.
        """
        result: IngestResult = self._ingest_pipeline.ingest_text(
            content=content,
            paper_id=paper_id,
            metadata=metadata,
        )
        return result.model_dump()

    def ask_question(
        self,
        question: str,
        paper_ids: Optional[List[str]] = None,
        sections: Optional[List[str]] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Answers a question grounded in target papers.

        Matches API contract:
        {
            "answer": "...",
            "sources": [
                {
                    "source_id": "S1",
                    "paper_id": "paper_123",
                    "page": 4,
                    "page_start": 4,
                    "page_end": 4,
                    "section": "Methodology",
                    "text": "...",
                    "score": 0.85,
                    "title": "Paper Title"
                }
            ],
            "paper_ids": ["paper_123"]
        }
        """
        filters = QueryFilters(sections=sections) if sections else None
        result: RAGResult = self._query_pipeline.answer_question(
            question=question,
            paper_ids=paper_ids,
            filters=filters,
            top_k=top_k,
        )
        return result.to_api_dict()

    def summarize_paper(
        self,
        paper_id: str,
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """
        Produces a structured research paper summary.
        """
        result: RAGResult = self._query_pipeline.summarize_paper(
            paper_id=paper_id,
            top_k=top_k,
        )
        return result.to_api_dict()

    def compare_papers(
        self,
        paper_ids: List[str],
        focus_area: Optional[str] = None,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Generates comparative analysis across multiple research papers.
        """
        result: RAGResult = self._query_pipeline.compare_papers(
            paper_ids=paper_ids,
            focus_area=focus_area,
            top_k=top_k,
        )
        return result.to_api_dict()

    def delete_paper(self, paper_id: str) -> int:
        """
        Removes all indexed vectors for a paper.
        """
        return self._ingest_pipeline.delete_paper(paper_id)

    def health_check(self) -> Dict[str, Any]:
        """
        Returns status of vector storage and pipeline readiness.
        """
        try:
            count = self._vector_repo.count_chunks()
            return {
                "status": "healthy",
                "total_indexed_chunks": count,
                "vectorstore": "chromadb",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Default singleton instance for quick import by backend routes
rag_client = RAGClient()
