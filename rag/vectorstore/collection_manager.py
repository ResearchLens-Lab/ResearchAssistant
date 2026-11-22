"""
ChromaDB collection management and lifecycle operations.
"""

import logging
from typing import Optional, Dict, Any
try:
    import chromadb
    from chromadb.api.models.Collection import Collection
except ImportError:
    chromadb = None
    Collection = Any
from rag.config.settings import settings
from rag.vectorstore.chroma_client import ChromaClientFactory

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Handles collection creation, retrieval, and deletion in ChromaDB.
    """

    def __init__(self, client: Optional[Any] = None):
        if chromadb is None:
            raise RuntimeError("ChromaDB is not installed in this model-free environment.")
        self.client = client or ChromaClientFactory.get_client()

    def get_or_create_collection(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Collection:
        coll_name = name or settings.chroma_collection_name
        embedding_model = settings.embedding_model
        embedding_provider = settings.embedding_provider
        if embedding_provider == "fastembed":
            import fastembed
            embedding_model = f"{embedding_model}@fastembed-{fastembed.__version__}"
        if name is None and settings.chroma_namespace_by_embedding:
            safe_model = "".join(c if c.isalnum() or c in "_-" else "_" for c in f"{embedding_provider}_{embedding_model}_chunkidv2")
            suffix = f"_{safe_model}_{settings.embedding_dimension}"[-58:]
            coll_name = f"{coll_name[:63-len(suffix)]}{suffix}"
        meta = metadata or {"hnsw:space": "cosine", "embedding_model": embedding_model,
                            "embedding_provider": embedding_provider,
                            "embedding_dimension": settings.embedding_dimension,
                            "chunk_id_schema": "document-scoped-v2"}

        logger.debug("Getting or creating collection '%s'", coll_name)
        return self.client.get_or_create_collection(
            name=coll_name,
            metadata=meta,
        )

    def get_collection(self, name: Optional[str] = None) -> Collection:
        coll_name = name or settings.chroma_collection_name
        return self.client.get_collection(name=coll_name)

    def delete_collection(self, name: Optional[str] = None) -> bool:
        coll_name = name or settings.chroma_collection_name
        try:
            self.client.delete_collection(name=coll_name)
            logger.info("Deleted collection '%s'", coll_name)
            return True
        except Exception as e:
            logger.warning("Could not delete collection exception_type=%s", type(e).__name__)
            return False

    def list_collections(self):
        return self.client.list_collections()
