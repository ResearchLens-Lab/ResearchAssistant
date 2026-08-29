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
        meta = metadata or {"hnsw:space": "cosine"}

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
            logger.warning("Could not delete collection '%s': %s", coll_name, e)
            return False

    def list_collections(self):
        return self.client.list_collections()
