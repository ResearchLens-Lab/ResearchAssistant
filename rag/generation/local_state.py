"""Persistent local response cache and daily outbound LLM call budget."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from rag.config.settings import settings


class LLMUsageBudgetExceeded(RuntimeError):
    pass


class SQLiteLLMState:
    # Bound response-cache disk growth without touching the call ledger.
    RESPONSE_CACHE_MAX_ROWS = 10_000

    def __init__(self, path: str | Path | None = None):
        cache_path = settings.embedding_cache_path or str(Path(settings.chroma_persist_dir) / "embedding_cache.sqlite3")
        self.path = Path(path or cache_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS llm_response_cache ("
                "cache_key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS llm_usage_budget ("
                "usage_day TEXT NOT NULL, provider TEXT NOT NULL, calls INTEGER NOT NULL, "
                "PRIMARY KEY(usage_day, provider))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_response_cache_created "
                "ON llm_response_cache(created_at)"
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
    def cache_key(model: str, system_prompt: str, user_prompt: str,
                  temperature: float, max_tokens: int, *, prompt_version: str = "v1",
                  normalized_question: str = "", scope: dict | None = None) -> str:
        import json
        value = "\0".join((model, str(temperature), str(max_tokens), prompt_version,
                            normalized_question, json.dumps(scope or {}, sort_keys=True, ensure_ascii=False),
                            system_prompt, user_prompt))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def get_response(self, key: str) -> str | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT response FROM llm_response_cache WHERE cache_key=?", (key,)).fetchone()
        return row[0] if row else None

    def put_response(self, key: str, response: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO llm_response_cache(cache_key, response) VALUES(?, ?)",
                (key, response),
            )
            connection.execute(
                "DELETE FROM llm_response_cache WHERE cache_key IN ("
                "SELECT cache_key FROM llm_response_cache "
                "ORDER BY created_at DESC, rowid DESC LIMIT -1 OFFSET ?)",
                (self.RESPONSE_CACHE_MAX_ROWS,),
            )

    def reserve_call(self, provider: str, daily_limit: int) -> int:
        day = datetime.now(timezone.utc).date().isoformat()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO llm_usage_budget(usage_day, provider, calls) VALUES(?, ?, 0)",
                (day, provider),
            )
            updated = connection.execute(
                "UPDATE llm_usage_budget SET calls=calls+1 WHERE usage_day=? AND provider=? AND calls < ?",
                (day, provider, daily_limit),
            )
            if updated.rowcount != 1:
                raise LLMUsageBudgetExceeded(
                    f"Daily {provider} generation budget ({daily_limit} calls) is exhausted. "
                    "Use the local evidence response or raise LLM_DAILY_CALL_BUDGET."
                )
            calls = connection.execute(
                "SELECT calls FROM llm_usage_budget WHERE usage_day=? AND provider=?", (day, provider)
            ).fetchone()[0]
            connection.commit()
            return int(calls)

