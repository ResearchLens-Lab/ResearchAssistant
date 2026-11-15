"""Vectorstore module exports with lazy loading for ChromaDB."""

__all__ = [
    "ChromaClientFactory",
    "CollectionManager",
    "VectorRepository",
    "VectorRecord",
]


def __getattr__(name: str):
    if name == "ChromaClientFactory":
        from rag.vectorstore.chroma_client import ChromaClientFactory
        return ChromaClientFactory
    elif name == "CollectionManager":
        from rag.vectorstore.collection_manager import CollectionManager
        return CollectionManager
    elif name in ("VectorRepository", "VectorRecord"):
        from rag.vectorstore.vector_repository import VectorRepository, VectorRecord
        return {"VectorRepository": VectorRepository, "VectorRecord": VectorRecord}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
