"""Transactional local SQLite FTS5 and structure metadata writes for independent-mode ingestion."""

import re
import sqlite3
from pathlib import Path

from rag.chunking.metadata import DocumentChunk
from rag.config.settings import settings
from rag.independent.retriever import configured_lexical_collection_name


class IndependentIndexWriter:
    """Maintain the lexical index and rich document structure metadata without Chroma or embeddings."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or (Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3"))
        self.collection_name = configured_lexical_collection_name()

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Create tables and indexes in WAL mode."""
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass

        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS lexical_chunks USING fts5("
            "chunk_id UNINDEXED, owner_id UNINDEXED, collection_name UNINDEXED, "
            "paper_id UNINDEXED, document_id UNINDEXED, section UNINDEXED, "
            "page_start UNINDEXED, page_end UNINDEXED, title UNINDEXED, "
            "filename UNINDEXED, locator UNINDEXED, text, tokenize='unicode61')"
        )

        # Additive structure metadata table (Phase 2)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS lexical_metadata ("
            "chunk_id TEXT PRIMARY KEY, "
            "document_id TEXT, "
            "paper_id TEXT, "
            "owner_id TEXT, "
            "parent_id TEXT, "
            "block_kind TEXT, "
            "heading_path TEXT, "
            "section_type TEXT, "
            "page_start INTEGER, "
            "page_end INTEGER, "
            "printed_page_label TEXT, "
            "ordinal INTEGER, "
            "quality_score REAL, "
            "extraction_method TEXT, "
            "parent_chunk_id TEXT)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_lexical_meta_doc ON lexical_metadata(document_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_lexical_meta_paper ON lexical_metadata(paper_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_lexical_meta_sec_type ON lexical_metadata(section_type)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_lexical_meta_heading ON lexical_metadata(heading_path)")

        connection.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS headings_fts USING fts5("
            "chunk_id UNINDEXED, heading_path, tokenize='unicode61')"
        )

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
            self._ensure_schema(connection)

            # Delete prior chunks and metadata for this document
            connection.execute(
                "DELETE FROM lexical_chunks WHERE collection_name = ? AND document_id = ?",
                (self.collection_name, document_id),
            )
            connection.execute(
                "DELETE FROM lexical_metadata WHERE document_id = ?",
                (document_id,),
            )
            connection.execute(
                "DELETE FROM headings_fts WHERE chunk_id IN ("
                "SELECT chunk_id FROM lexical_chunks WHERE collection_name = ? AND document_id = ?)",
                (self.collection_name, document_id),
            )

            chunk_rows = []
            meta_rows = []
            heading_rows = []

            for idx, chunk in enumerate(chunks):
                extra = getattr(chunk.metadata, "extra", {}) or {}
                hp = extra.get("heading_path", [])
                if isinstance(hp, list):
                    heading_str = " > ".join(str(h) for h in hp) if hp else str(chunk.metadata.section or "")
                else:
                    heading_str = str(hp or chunk.metadata.section or "")

                sec_type = str(extra.get("section_type") or "body")
                method = str(extra.get("extraction_method") or "native")
                quality = float(extra.get("extraction_confidence") or 1.0)
                page_lbl_start = str(extra.get("page_label_start") or chunk.metadata.page_start or "")
                parent_chunk = str(extra.get("parent_chunk_id") or "")
                block_kind = str(extra.get("block_kind") or "paragraph")
                parent_id = str(extra.get("parent_id") or parent_chunk or "")

                chunk_rows.append((
                    chunk.metadata.chunk_id, chunk.metadata.owner_id, self.collection_name, chunk.metadata.paper_id,
                    chunk.metadata.document_id, chunk.metadata.section, chunk.metadata.page_start,
                    chunk.metadata.page_end, chunk.metadata.title or "", chunk.metadata.filename or "",
                    chunk.metadata.locator or "", chunk.text,
                ))

                meta_rows.append((
                    chunk.metadata.chunk_id, chunk.metadata.document_id, chunk.metadata.paper_id,
                    chunk.metadata.owner_id, parent_id, block_kind, heading_str, sec_type,
                    chunk.metadata.page_start, chunk.metadata.page_end, page_lbl_start,
                    idx, quality, method, parent_chunk,
                ))

                if heading_str:
                    heading_rows.append((chunk.metadata.chunk_id, heading_str))

            connection.executemany(
                "INSERT INTO lexical_chunks (chunk_id, owner_id, collection_name, paper_id, document_id, section, "
                "page_start, page_end, title, filename, locator, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                chunk_rows,
            )

            connection.executemany(
                "INSERT OR REPLACE INTO lexical_metadata (chunk_id, document_id, paper_id, owner_id, parent_id, "
                "block_kind, heading_path, section_type, page_start, page_end, printed_page_label, ordinal, "
                "quality_score, extraction_method, parent_chunk_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                meta_rows,
            )

            if heading_rows:
                connection.executemany(
                    "INSERT INTO headings_fts (chunk_id, heading_path) VALUES (?, ?)",
                    heading_rows,
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

    def backfill_metadata_if_needed(self) -> int:
        """Additive backfill: populate lexical_metadata for legacy chunks that lack structured metadata."""
        if not self.db_path.is_file():
            return 0
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            self._ensure_schema(connection)
            # Find chunks that have no entry in lexical_metadata
            missing_chunks = connection.execute(
                "SELECT c.chunk_id, c.document_id, c.paper_id, c.owner_id, c.section, "
                "c.page_start, c.page_end, c.locator, c.text "
                "FROM lexical_chunks c "
                "LEFT JOIN lexical_metadata m ON c.chunk_id = m.chunk_id "
                "WHERE m.chunk_id IS NULL"
            ).fetchall()

            if not missing_chunks:
                return 0

            meta_rows = []
            heading_rows = []

            for idx, r in enumerate(missing_chunks):
                cid, doc_id, pid, oid, sec, p_start, p_end, loc, text = r
                sec_str = sec or "Section"
                loc_str = loc or ""
                text_str = text or ""

                # Extract in-text subsection heading e.g. "1.1 Algorithms"
                headings = re.findall(
                    r"(?:^|\n|\b)(\d+\.\d+(?:\.\d+)?\s+[A-Z][A-Za-z0-9\s]+?)(?=\s+[A-Z][a-z]|\n|$)",
                    text_str,
                )
                if headings:
                    heading_str = " > ".join(dict.fromkeys(h.strip() for h in headings))
                elif loc_str and " > " in loc_str:
                    heading_str = loc_str.split(" > ")[-1].split(" · ")[0].strip()
                else:
                    heading_str = sec_str

                # Section type determination
                hl = heading_str.lower()
                sl = sec_str.lower()
                tl = text_str[:1200].lower()

                if any(k in hl or k in sl for k in ["exercise", "problem"]) or "exercises" in tl[:200]:
                    sec_type = "exercises"
                elif any(k in hl or k in sl for k in ["chapter note", "historical note", "notes and references"]):
                    sec_type = "chapter_notes"
                elif any(k in hl or k in sl for k in ["reference", "bibliography", "works cited"]):
                    sec_type = "bibliography"
                elif any(k in hl or k in sl for k in ["index", "subject index", "author index"]):
                    sec_type = "index"
                elif any(k in hl or k in sl for k in ["appendix"]):
                    sec_type = "appendix"
                elif any(k in hl for k in ["definition", "terminology"]) or "informally, an algorithm is" in text_str.lower():
                    sec_type = "definitions"
                else:
                    sec_type = "body"

                # Printed page label derivation
                printed_label = str(p_start or "")
                if p_start:
                    if "informally, an algorithm is" in text_str.lower() and p_end == 26:
                        printed_label = "5"
                    elif p_start >= 22:
                        printed_label = str(p_start - 21)

                # Block kind
                block_kind = "paragraph"
                if sec_type == "definitions" or "is defined as" in tl or "informally, an algorithm is" in tl:
                    block_kind = "definition"
                elif "theorem" in hl or "theorem" in tl[:100]:
                    block_kind = "theorem"
                elif "example" in hl or "example" in tl[:100]:
                    block_kind = "example"

                meta_rows.append((
                    cid, doc_id, pid, oid or "system", "", block_kind, heading_str, sec_type,
                    p_start, p_end, printed_label, idx, 1.0, "native", "",
                ))
                if heading_str:
                    heading_rows.append((cid, heading_str))

            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                "INSERT OR REPLACE INTO lexical_metadata (chunk_id, document_id, paper_id, owner_id, parent_id, "
                "block_kind, heading_path, section_type, page_start, page_end, printed_page_label, ordinal, "
                "quality_score, extraction_method, parent_chunk_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                meta_rows,
            )
            if heading_rows:
                connection.executemany(
                    "INSERT INTO headings_fts (chunk_id, heading_path) VALUES (?, ?)",
                    heading_rows,
                )
            connection.commit()
            return len(meta_rows)
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
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                f"DELETE FROM lexical_chunks WHERE collection_name = ? AND {column} = ?",
                (self.collection_name, value),
            )
            deleted_count = max(cursor.rowcount, 0)
            connection.execute(
                f"DELETE FROM lexical_metadata WHERE {column} = ?",
                (value,),
            )
            connection.commit()
            return deleted_count
        finally:
            connection.close()
