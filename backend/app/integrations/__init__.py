"""
Backend Integrations.

`RAGClient`/`rag_client` (Gorav's boundary) are exposed lazily so importing
this package does not pull in the RAG dependency chain (ChromaDB, embedders)
until RAG is actually used. The public interface is unchanged:
`from backend.app.integrations import rag_client` still works.
"""

from typing import Any

__all__ = ["RAGClient", "rag_client"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from backend.app.integrations import rag_client as _rag_client_module

        if name == "RAGClient":
            return _rag_client_module.RAGClient
        return _rag_client_module.rag_client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
