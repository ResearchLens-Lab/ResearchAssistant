"""Transactional local SQLite FTS5 writes for independent-mode ingestion."""

import sqlite3
from pathlib import Path

from rag.chunking.metadata import DocumentChunk
from rag.config.settings import settings
from rag.independent.retriever import configured_lexical_collection_name


class IndependentIndexWriter:
    """Maintain the existing lexical index without Chroma or embeddings."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or (Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"))
        self.collection_name = configured_lexical_collection_name()

    def replace_document_chunks(self, document_id: str, chunks: list[DocumentChunk]) -> int:
        ids = [chunk.metadata.chunk_id for chunk in chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("Chunk IDs are not unique within the document.")
        # SEC-001: Mandatory fail-fast validation of owner_id
        for chunk in chunks:
            owner_id = getattr(chunk.metadata, "owner_id", None)
            if not owner_id or not str(owner_id).strip():
                raise ValueError(f"owner_id is required for chunk {chunk.metadata.chunk_id} (SEC-001)")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks USING fts5(chunk_id UNINDEXED, owner_id UNINDEXED, collection_name UNINDEXED, paper_id UNINDEXED, document_id UNINDEXED, section UNINDEXED, page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61')"
            )
            connection.execute(
                "DELETE FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection_name, document_id),
            )
            connection.executemany(
                "INSERT INTO lexical_chunks (chunk_id, owner_id, collection_name, paper_id, document_id, section, page_start, page_end, title, filename, locator, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(
                    chunk.metadata.chunk_id, chunk.metadata.owner_id, self.collection_name, chunk.metadata.paper_id,
                    chunk.metadata.document_id, chunk.metadata.section, chunk.metadata.page_start,
                    chunk.metadata.page_end, chunk.metadata.title or "", chunk.metadata.filename or "",
                    chunk.metadata.locator or "", chunk.text,
                ) for chunk in chunks],
            )
            actual_ids = [row[0] for row in connection.execute(
                "SELECT chunk_id FROM lexical_chunks WHERE collection_name = ? AND document_id = ? ORDER BY chunk_id",
                (self.collection_name, document_id),
            )]
            if len(actual_ids) != len(ids) or set(actual_ids) != set(ids):
                raise RuntimeError("The committed lexical chunk IDs do not match the new document chunks.")
            connection.commit()
            return len(actual_ids)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def delete_document(self, document_id: str) -> int:
        return self._delete("document_id", document_id)

    def delete_paper(self, paper_id: str) -> int:
        return self._delete("paper_id", paper_id)

    def count_document(self, document_id: str) -> dict:
        if not self.db_path.is_file():
            return {"lexical_only": True, "lexical_count": 0, "lexical_unique_count": 0}
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            rows = connection.execute(
                "SELECT chunk_id FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection_name, document_id),
            ).fetchall()
        finally:
            connection.close()
        ids = [row[0] for row in rows]
        return {"lexical_only": True, "lexical_count": len(ids), "lexical_unique_count": len(set(ids))}

    def get_document_index_status(self, document_id: str) -> dict:
        """Inspect chunk records in lexical_chunks to determine index version, section structure, and staleness."""
        if not self.db_path.is_file():
            return {"exists": False, "chunk_count": 0, "is_stale": False, "index_version": 2, "sections": []}
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            rows = connection.execute(
                "SELECT chunk_id, section, page_start, page_end FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection_name, document_id),
            ).fetchall()
        finally:
            connection.close()
        if not rows:
            return {"exists": False, "chunk_count": 0, "is_stale": False, "index_version": 2, "sections": []}
        sections = [r[1] for r in rows if r[1]]
        is_stale = False
        if len(rows) == 1:
            chunk = rows[0]
            p_start, p_end = chunk[2], chunk[3]
            sec = chunk[1] or ""
            if (p_start and p_end and p_end > p_start) or sec in ("Header / Abstract", "Abstract", "Header", ""):
                is_stale = True
        elif all(s in ("Header / Abstract", "Abstract", "Header", "", None) for s in sections):
            is_stale = True
        return {
            "exists": True,
            "chunk_count": len(rows),
            "sections": list(dict.fromkeys(sections)),
            "is_stale": is_stale,
            "index_version": 1 if is_stale else 2,
        }

    def count_all(self) -> int:
        if not self.db_path.is_file():
            return 0
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            row = connection.execute(
                "SELECT count(*) FROM lexical_chunks WHERE collection_name = ?", (self.collection_name,)
            ).fetchone()
            return int(row[0] or 0)
        finally:
            connection.close()

    def _delete(self, column: str, value: str) -> int:
        if column not in {"document_id", "paper_id"}:
            raise ValueError("Unsupported index deletion scope.")
        if not self.db_path.is_file():
            return 0
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            cursor = connection.execute(
                f"DELETE FROM lexical_chunks WHERE collection_name = ? AND {column} = ?",
                (self.collection_name, value),
            )
            connection.commit()
            return max(cursor.rowcount, 0)
        finally:
            connection.close()
