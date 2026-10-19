"""
ChromaDB client factory and connection manager.
Supports PersistentClient (local storage) and HttpClient (remote server).
"""

import os
import logging
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from rag.config.settings import settings

logger = logging.getLogger(__name__)


class ChromaClientFactory:
    """
    Manages ChromaDB client lifecycle and connection health.
    """

    _instance: Optional[chromadb.ClientAPI] = None
    _client_persist_dirs: dict[int, str] = {}

    @classmethod
    def get_client(
        cls,
        persist_dir: Optional[str] = None,
        use_http: Optional[bool] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        force_new: bool = False,
    ) -> chromadb.ClientAPI:
        if cls._instance is not None and not force_new:
            return cls._instance

        http_mode = use_http if use_http is not None else settings.chroma_use_http

        if http_mode:
            h = host or settings.chroma_host
            p = port or settings.chroma_port
            logger.info("Connecting to remote ChromaDB at %s:%d", h, p)
            client = chromadb.HttpClient(host=h, port=p)
        else:
            p_dir = persist_dir or settings.chroma_persist_dir
            os.makedirs(p_dir, exist_ok=True)
            logger.info("Using local PersistentClient")
            client = chromadb.PersistentClient(
                path=p_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            cls._client_persist_dirs[id(client)] = p_dir

        if not force_new:
            cls._instance = client

        return client

    @classmethod
    def reset_client(cls) -> None:
        """Resets cached client instance (useful in tests)."""
        cls._instance = None
        cls._client_persist_dirs.clear()

    @classmethod
    def shutdown_client(cls) -> None:
        """Close the cached local/remote client's system before dropping its handle."""
        client = cls._instance
        if client is not None:
            system = getattr(client, "_system", None)
            stop = getattr(system, "stop", None)
            if callable(stop):
                stop()
        cls.reset_client()

    @classmethod
    def persist_dir_for(cls, client: chromadb.ClientAPI) -> str:
        return cls._client_persist_dirs.get(id(client), settings.chroma_persist_dir)
