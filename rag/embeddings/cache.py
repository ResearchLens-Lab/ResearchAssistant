"""Small persistent cache for embeddings, keyed by model identity and text hash."""

from __future__ import annotations

import hashlib
import sqlite3
import struct
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


class SQLiteEmbeddingCache:
    """Stores vectors without retaining source text; safe across worker threads."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS embedding_cache ("
                "model_version TEXT NOT NULL, content_sha256 TEXT NOT NULL, dimension INTEGER NOT NULL, "
                "vector BLOB NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "PRIMARY KEY(model_version, content_sha256))"
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, model_version: str, text: str) -> Optional[list[float]]:
        key = self.content_hash(text)
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT dimension, vector FROM embedding_cache WHERE model_version=? AND content_sha256=?",
                (model_version, key),
            ).fetchone()
        if not row:
            return None
        dimension, blob = row
        if len(blob) != dimension * 4:
            return None
        return list(struct.unpack(f"<{dimension}f", blob))

    def get_many(self, model_version: str, texts: list[str]) -> dict[str, list[float]]:
        hashes = list(dict.fromkeys(self.content_hash(text) for text in texts))
        if not hashes:
            return {}
        found: dict[str, list[float]] = {}
        with self._lock, self._connect() as connection:
            for start in range(0, len(hashes), 500):
                batch = hashes[start:start + 500]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT content_sha256, dimension, vector FROM embedding_cache "
                    f"WHERE model_version=? AND content_sha256 IN ({placeholders})",
                    (model_version, *batch),
                ).fetchall()
                for key, dimension, blob in rows:
                    if len(blob) == dimension * 4:
                        found[key] = list(struct.unpack(f"<{dimension}f", blob))
        return found

    def put(self, model_version: str, text: str, vector: list[float]) -> None:
        key = self.content_hash(text)
        blob = struct.pack(f"<{len(vector)}f", *vector)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO embedding_cache(model_version, content_sha256, dimension, vector) "
                "VALUES(?, ?, ?, ?)",
                (model_version, key, len(vector), blob),
            )

    def put_many(self, model_version: str, items: list[tuple[str, list[float]]]) -> None:
        rows = [
            (model_version, self.content_hash(text), len(vector), struct.pack(f"<{len(vector)}f", *vector))
            for text, vector in items
        ]
        if not rows:
            return
        with self._lock, self._connect() as connection:
            connection.executemany(
                "INSERT OR REPLACE INTO embedding_cache(model_version, content_sha256, dimension, vector) "
                "VALUES(?, ?, ?, ?)",
                rows,
            )

