"""
Vector repository abstraction over ChromaDB.
Provides unified upsert, querying with metadata filtering, and document deletion.
Enforces deterministic IDs and source provenance.
"""

import logging
import re
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from rag.chunking.metadata import DocumentChunk, ChunkMetadata
from rag.vectorstore.collection_manager import CollectionManager
from rag.vectorstore.chroma_client import ChromaClientFactory

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

        # Chroma upsert updates existing IDs or inserts new ones.
        chroma_started = time.perf_counter()
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        chroma_seconds = time.perf_counter() - chroma_started
        lexical_started = time.perf_counter()
        # FTS5 is part of the indexing transaction contract. Surface failures so
        # ingestion can clean the Chroma half instead of reporting false success.
        self._upsert_lexical(chunks)
        lexical_seconds = time.perf_counter() - lexical_started

        logger.info(
            "Vector indexing complete chunks=%d chroma_seconds=%.3f lexical_seconds=%.3f",
            len(chunks), chroma_seconds, lexical_seconds,
        )
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

    def query_lexical(self, query: str, where: Optional[Dict[str, Any]] = None, limit: int = 1000) -> List[VectorRecord]:
        """Search the synchronized SQLite FTS5 index using BM25 ranking."""
        terms = list(dict.fromkeys(re.findall(r"[\w]+", query.lower())))
        if not terms:
            return []
        self._ensure_lexical_index()
        constraints, values = self._lexical_constraints(where)
        clauses = ["collection_name = ?", "lexical_chunks MATCH ?"] + constraints
        params = [self.collection.name, " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms), *values, limit]
        sql = "SELECT chunk_id, paper_id, document_id, section, page_start, page_end, title, filename, locator, text, bm25(lexical_chunks) AS score FROM lexical_chunks WHERE " + " AND ".join(clauses) + " ORDER BY score ASC LIMIT ?"
        with self._lexical_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            VectorRecord(
                id=row[0], text=row[9], similarity_score=1.0 / (60 + rank),
                metadata=ChunkMetadata(
                    chunk_id=row[0], paper_id=row[1], document_id=row[2], section=row[3] or "Main Content",
                    page_start=int(row[4]) if row[4] is not None else None,
                    page_end=int(row[5]) if row[5] is not None else None,
                    title=row[6] or None, filename=row[7] or None, locator=row[8] or None,
                    chunk_index=0,
                ),
            ) for rank, row in enumerate(rows, start=1)
        ]

    @contextmanager
    def _lexical_connection(self):
        persist_dir = ChromaClientFactory.persist_dir_for(self.collection_manager.client)
        path = Path(persist_dir) / "researchlens_lexical.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks USING fts5(chunk_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61')")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _lexical_constraints(where: Optional[Dict[str, Any]]):
        clauses, params = [], []
        if not where:
            return clauses, params
        items = where.get("$and", [where]) if isinstance(where, dict) else []
        if not isinstance(items, list):
            return ["1 = 0"], []
        allowed = {"paper_id", "document_id", "section"}
        for item in items:
            if not isinstance(item, dict):
                return ["1 = 0"], []
            for key, value in item.items():
                if key not in allowed:
                    return ["1 = 0"], []
                values = value.get("$in") if isinstance(value, dict) else [value]
                if not isinstance(values, list) or not values:
                    return ["1 = 0"], []
                clauses.append(f"{key} IN ({','.join('?' for _ in values)})")
                params.extend(str(v) for v in values)
        return clauses, params

    def _upsert_lexical(self, chunks: List[DocumentChunk]) -> None:
        collection_name = self.collection.name
        with self._lexical_connection() as conn:
            conn.executemany(
                "DELETE FROM lexical_chunks WHERE collection_name = ? AND chunk_id = ?",
                ((collection_name, chunk.metadata.chunk_id) for chunk in chunks),
            )
            conn.executemany(
                "INSERT INTO lexical_chunks (chunk_id, collection_name, paper_id, document_id, section, page_start, page_end, title, filename, locator, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ((
                    chunk.metadata.chunk_id, collection_name, chunk.metadata.paper_id,
                    chunk.metadata.document_id, chunk.metadata.section, chunk.metadata.page_start,
                    chunk.metadata.page_end, chunk.metadata.title or "", chunk.metadata.filename or "",
                    chunk.metadata.locator or "", chunk.text,
                ) for chunk in chunks),
            )

    def _ensure_lexical_index(self) -> None:
        with self._lexical_connection() as conn:
            indexed = conn.execute("SELECT count(*) FROM lexical_chunks WHERE collection_name = ?", (self.collection.name,)).fetchone()[0]
        if indexed == self.collection.count():
            return
        # Backfill older Chroma collections without deleting or mutating vectors.
        records = []
        offset = 0
        page_size = 1000
        while True:
            batch = self.collection.get(limit=page_size, offset=offset, include=["documents", "metadatas"])
            ids = batch.get("ids", [])
            if not ids:
                break
            for chunk_id, doc, meta in zip(ids, batch.get("documents", []), batch.get("metadatas", [])):
                m = ChunkMetadata.from_chroma_metadata(meta)
                records.append(DocumentChunk(text=doc, metadata=m))
            offset += len(ids)
            if len(ids) < page_size:
                break
        with self._lexical_connection() as conn:
            conn.execute("DELETE FROM lexical_chunks WHERE collection_name = ?", (self.collection.name,))
        for start in range(0, len(records), 500):
            self._upsert_lexical(records[start:start + 500])

    def delete_paper_chunks(self, paper_id: str) -> int:
        """
        Deletes all chunks belonging to a paper.
        """
        existing = self.collection.get(where={"paper_id": paper_id})
        count = len(existing.get("ids", []))
        if count > 0:
            self.collection.delete(where={"paper_id": paper_id})
        # Always remove FTS rows, including orphan rows from a partial index.
        with self._lexical_connection() as conn:
            conn.execute("DELETE FROM lexical_chunks WHERE collection_name = ? AND paper_id = ?", (self.collection.name, paper_id))
        logger.info("Deleted %d chunks for paper_id='%s'", count, paper_id)
        return count

    def delete_document_chunks(self, document_id: str) -> int:
        """
        Deletes all chunks belonging to a document.
        """
        existing = self.collection.get(where={"document_id": document_id})
        count = len(existing.get("ids", []))
        if count > 0:
            self.collection.delete(where={"document_id": document_id})
        # Always remove lexical rows: a previous partial failure may have left
        # FTS entries even when Chroma has none.
        with self._lexical_connection() as conn:
            conn.execute("DELETE FROM lexical_chunks WHERE collection_name = ? AND document_id = ?", (self.collection.name, document_id))
        logger.info("Deleted %d Chroma chunks for document_id='%s'", count, document_id)
        return count

    def reconcile_document_chunks(self, document_id: str, expected_ids: set[str]) -> None:
        """Remove stale IDs left by older/partial attempts for this document."""
        chroma_ids = set(self.collection.get(where={"document_id": document_id}).get("ids", []))
        stale_chroma = chroma_ids - expected_ids
        if stale_chroma:
            self.collection.delete(ids=sorted(stale_chroma))
        with self._lexical_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection.name, document_id),
            ).fetchall()
            stale_fts = {row[0] for row in rows} - expected_ids
            if stale_fts:
                conn.executemany(
                    "DELETE FROM lexical_chunks WHERE collection_name = ? AND document_id = ? AND chunk_id = ?",
                    ((self.collection.name, document_id, chunk_id) for chunk_id in stale_fts),
                )

    def document_index_counts(self, document_id: str) -> Dict[str, Any]:
        """Inspect the active collection and FTS5 rows without repairing either."""
        chroma_ids = set(self.collection.get(where={"document_id": document_id}).get("ids", []))
        with self._lexical_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection.name, document_id),
            ).fetchall()
        fts_id_list = [row[0] for row in rows]
        fts_ids = set(fts_id_list)
        return {
            "collection_name": self.collection.name,
            "chroma_count": len(chroma_ids),
            "fts_count": len(fts_id_list),
            "unique_fts_count": len(fts_ids),
            "ids_match": chroma_ids == fts_ids and len(fts_id_list) == len(fts_ids),
        }

    def count_chunks(self, where: Optional[Dict[str, Any]] = None) -> int:
        if where:
            res = self.collection.get(where=where)
            return len(res.get("ids", []))
        return self.collection.count()
