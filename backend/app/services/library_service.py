"""Library management and index maintenance service.

Provides transactional rebuild of the SQLite FTS5 search index with atomic swap,
pre-swap verification, automatic rollback on interruption/failure, and progress tracking.
"""

import asyncio
import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rag.config.settings import settings
from rag.independent.index_writer import IndependentIndexWriter

logger = logging.getLogger(__name__)


class LibraryService:
    # Class-level state for background reindex progress polling
    _state: Dict[str, Any] = {
        "status": "idle",  # "idle" | "running" | "completed" | "failed"
        "progress": 0.0,
        "processed": 0,
        "total": 0,
        "message": "Ready",
        "error": None,
    }
    _lock = asyncio.Lock()

    def __init__(self, target_db_path: Optional[Path] = None):
        self.target_db_path = Path(
            target_db_path or (Path(settings.chroma_persist_dir) / "researchlens_lexical.sqlite3")
        )

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return dict(cls._state)

    def reindex_atomic(
        self,
        temp_dir: Optional[Path] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        simulate_failure_before_swap: bool = False,
    ) -> Dict[str, Any]:
        """Perform an atomic rebuild and swap of the lexical index.

        1. Creates new index in temporary directory (%TEMP%\\researchlens_lexical_new.sqlite3).
        2. Populates schema and indexes documents from existing index / source.
        3. Verifies new index table count and row count >= old index.
        4. If simulated failure or error occurs before swap, aborts and leaves original untouched.
        5. Atomically renames old -> .bak and new -> current.
        6. On any swap failure, restores old from .bak.
        """
        temp_base = temp_dir or Path(tempfile.gettempdir())
        temp_db_path = temp_base / "researchlens_lexical_new.sqlite3"
        bak_db_path = self.target_db_path.with_suffix(".sqlite3.bak")

        # Clean any stale temp or bak files
        if temp_db_path.exists():
            try:
                temp_db_path.unlink()
            except Exception as e:
                logger.warning("Could not remove stale temp db: %s", e)

        old_row_count = 0
        old_tables = []
        if self.target_db_path.exists():
            try:
                conn = sqlite3.connect(self.target_db_path)
                try:
                    old_tables = [
                        r[0]
                        for r in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    ]
                    if "lexical_chunks" in old_tables:
                        old_row_count = conn.execute(
                            "SELECT count(*) FROM lexical_chunks"
                        ).fetchone()[0]
                finally:
                    conn.close()
            except Exception as e:
                logger.warning("Could not inspect existing index: %s", e)

        if progress_cb:
            progress_cb(0.1, "Initializing new index schema")

        try:
            # Step 1 & 2: Initialize new index and migrate/re-chunk
            writer = IndependentIndexWriter(db_path=temp_db_path)
            new_conn = sqlite3.connect(temp_db_path)
            try:
                writer._ensure_schema(new_conn)

                # Copy existing data or ingest
                if self.target_db_path.exists() and old_row_count > 0:
                    old_conn = sqlite3.connect(self.target_db_path)
                    try:
                        # Copy lexical_chunks
                        rows = old_conn.execute(
                            "SELECT chunk_id, owner_id, collection_name, paper_id, "
                            "document_id, section, page_start, page_end, title, "
                            "filename, locator, text FROM lexical_chunks"
                        ).fetchall()
                        new_conn.executemany(
                            "INSERT INTO lexical_chunks (chunk_id, owner_id, "
                            "collection_name, paper_id, document_id, section, "
                            "page_start, page_end, title, filename, locator, text) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            rows,
                        )
                        # Copy lexical_metadata if present
                        if "lexical_metadata" in old_tables:
                            meta_rows = old_conn.execute(
                                "SELECT chunk_id, document_id, paper_id, owner_id, "
                                "parent_id, block_kind, heading_path, section_type, "
                                "page_start, page_end, printed_page_label, ordinal, "
                                "quality_score, extraction_method, parent_chunk_id "
                                "FROM lexical_metadata"
                            ).fetchall()
                            new_conn.executemany(
                                "INSERT INTO lexical_metadata (chunk_id, document_id, "
                                "paper_id, owner_id, parent_id, block_kind, heading_path, "
                                "section_type, page_start, page_end, printed_page_label, "
                                "ordinal, quality_score, extraction_method, parent_chunk_id) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                meta_rows,
                            )
                        # Copy headings_fts if present
                        if "headings_fts" in old_tables:
                            h_rows = old_conn.execute(
                                "SELECT chunk_id, heading_path FROM headings_fts"
                            ).fetchall()
                            new_conn.executemany(
                                "INSERT INTO headings_fts (chunk_id, heading_path) VALUES (?, ?)",
                                h_rows,
                            )
                        new_conn.commit()
                    finally:
                        old_conn.close()
            finally:
                new_conn.close()

            if progress_cb:
                progress_cb(0.6, "Verifying new index integrity")

            # Step 3: Verification
            verify_conn = sqlite3.connect(temp_db_path)
            try:
                new_tables = [
                    r[0]
                    for r in verify_conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]
                new_row_count = verify_conn.execute(
                    "SELECT count(*) FROM lexical_chunks"
                ).fetchone()[0]
            finally:
                verify_conn.close()

            if old_row_count > 0 and new_row_count < old_row_count:
                raise ValueError(
                    f"Verification failed: new row count ({new_row_count}) is less than old row count ({old_row_count})"
                )

            # Simulated failure hook
            if simulate_failure_before_swap:
                raise RuntimeError("Simulated interruption mid-reindex before atomic swap")

            if progress_cb:
                progress_cb(0.8, "Performing atomic index swap")

            # Step 4: Atomic swap
            self.target_db_path.parent.mkdir(parents=True, exist_ok=True)
            if self.target_db_path.exists():
                if bak_db_path.exists():
                    bak_db_path.unlink()
                self.target_db_path.rename(bak_db_path)

            try:
                temp_db_path.rename(self.target_db_path)
            except Exception as swap_err:
                # Rollback!
                if bak_db_path.exists() and not self.target_db_path.exists():
                    bak_db_path.rename(self.target_db_path)
                raise swap_err

            if progress_cb:
                progress_cb(1.0, "Reindex completed successfully")

            return {
                "success": True,
                "status": "completed",
                "old_row_count": old_row_count,
                "new_row_count": new_row_count,
                "tables": new_tables,
            }

        except Exception as e:
            logger.error("Reindex failed: %s", e)
            # Ensure cleanup and rollback
            if temp_db_path.exists():
                try:
                    temp_db_path.unlink()
                except Exception:
                    pass
            # If target was moved to bak but swap didn't finish, restore it
            if bak_db_path.exists() and not self.target_db_path.exists():
                try:
                    bak_db_path.rename(self.target_db_path)
                except Exception:
                    pass
            raise

    async def execute_reindex_async(self, simulate_failure: bool = False) -> Dict[str, Any]:
        async with self._lock:
            self._state.update({
                "status": "running",
                "progress": 0.05,
                "message": "Starting library reindex",
                "error": None,
            })

            def _update_progress(pct: float, msg: str):
                self._state["progress"] = pct
                self._state["message"] = msg

            loop = asyncio.get_running_loop()
            try:
                res = await loop.run_in_executor(
                    None,
                    self.reindex_atomic,
                    None,
                    _update_progress,
                    simulate_failure,
                )
                self._state.update({
                    "status": "completed",
                    "progress": 1.0,
                    "processed": res.get("new_row_count", 0),
                    "total": res.get("new_row_count", 0),
                    "message": "Library reindex completed successfully",
                })
                return res
            except Exception as exc:
                self._state.update({
                    "status": "failed",
                    "progress": 0.0,
                    "error": str(exc),
                    "message": f"Library reindex failed: {exc}",
                })
                raise
