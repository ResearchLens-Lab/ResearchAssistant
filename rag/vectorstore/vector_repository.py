"""
Vector repository abstraction over ChromaDB.
Provides unified upsert, querying with metadata filtering, and document deletion.
Enforces deterministic IDs and source provenance.
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from rag.chunking.metadata import DocumentChunk, ChunkMetadata
from rag.vectorstore.collection_manager import CollectionManager

logger = logging.getLogger(__name__)


class VectorRecord(BaseModel):
    id: str
    text: str
    metadata: ChunkMetadata
    distance: Optional[float] = None
    similarity_score: Optional[float] = None


class VectorRepository:
    """
    Data access layer for vector operations in ChromaDB.
    """

    def __init__(self, collection_manager: Optional[CollectionManager] = None):
        self.collection_manager = collection_manager or CollectionManager()
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.collection_manager.get_or_create_collection()
        return self._collection

    def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> int:
        """
        Upserts document chunks with their embeddings and metadata into ChromaDB.
        Idempotent due to deterministic chunk IDs.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks count ({len(chunks)}) does not match embeddings count ({len(embeddings)})")

        ids = [chunk.metadata.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata.to_chroma_metadata() for chunk in chunks]

        # Chroma upsert updates existing IDs or inserts new ones
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info("Successfully upserted %d vector chunks into ChromaDB", len(chunks))
        return len(chunks)

    def query_vectors(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[VectorRecord]:
        """
        Executes vector similarity search with optional ChromaDB metadata filters.
        """
        query_params: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_params["where"] = where

        results = self.collection.query(**query_params)

        records: List[VectorRecord] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return records

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        for chunk_id, doc_text, meta_dict, dist in zip(ids, docs, metas, distances):
            # Cosine distance to similarity: similarity = 1 - distance (or max(0, 1 - dist/2))
            # ChromaDB cosine distance range is [0, 2], where 0 is identical.
            similarity = max(0.0, 1.0 - float(dist))

            chunk_meta = ChunkMetadata.from_chroma_metadata(meta_dict)
            records.append(
                VectorRecord(
                    id=chunk_id,
                    text=doc_text,
                    metadata=chunk_meta,
                    distance=float(dist),
                    similarity_score=similarity,
                )
            )

        return records

    def delete_paper_chunks(self, paper_id: str) -> int:
        """
        Deletes all chunks belonging to a paper.
        """
        try:
            # Query existing IDs for this paper
            existing = self.collection.get(where={"paper_id": paper_id})
            count = len(existing.get("ids", []))
            if count > 0:
                self.collection.delete(where={"paper_id": paper_id})
                logger.info("Deleted %d chunks for paper_id='%s'", count, paper_id)
            return count
        except Exception as e:
            logger.error("Failed to delete chunks for paper_id '%s': %s", paper_id, e)
            return 0

    def delete_document_chunks(self, document_id: str) -> int:
        """
        Deletes all chunks belonging to a document.
        """
        try:
            existing = self.collection.get(where={"document_id": document_id})
            count = len(existing.get("ids", []))
            if count > 0:
                self.collection.delete(where={"document_id": document_id})
                logger.info("Deleted %d chunks for document_id='%s'", count, document_id)
            return count
        except Exception as e:
            logger.error("Failed to delete chunks for document_id '%s': %s", document_id, e)
            return 0

    def count_chunks(self, where: Optional[Dict[str, Any]] = None) -> int:
        if where:
            res = self.collection.get(where=where)
            return len(res.get("ids", []))
        return self.collection.count()
