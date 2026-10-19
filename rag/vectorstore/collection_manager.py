"""
ChromaDB collection management and lifecycle operations.
"""

import logging
from typing import Optional, Dict, Any
import chromadb
from chromadb.api.models.Collection import Collection
from rag.config.settings import settings
from rag.vectorstore.chroma_client import ChromaClientFactory

logger = logging.getLogger(__name__)


class CollectionManager:
    """
    Handles collection creation, retrieval, and deletion in ChromaDB.
    """

    def __init__(self, client: Optional[chromadb.ClientAPI] = None):
        self.client = client or ChromaClientFactory.get_client()

    def get_or_create_collection(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Collection:
        coll_name = name or settings.chroma_collection_name
        embedding_model = settings.embedding_model
        if settings.embedding_provider == "openai" and not embedding_model.startswith("text-embedding"):
            embedding_model = "text-embedding-3-small"
        if name is None and settings.chroma_namespace_by_embedding:
            safe_model = "".join(c if c.isalnum() or c in "_-" else "_" for c in embedding_model)
            suffix = f"_{safe_model}_{settings.embedding_dimension}"
            coll_name = f"{coll_name[:63-len(suffix)]}{suffix}"
        meta = metadata or {"hnsw:space": "cosine", "embedding_model": embedding_model,
                            "embedding_dimension": settings.embedding_dimension}

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
