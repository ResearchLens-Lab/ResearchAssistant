"""
Constructs ChromaDB metadata filters from QueryFilters or paper_ids.
SECURITY: All queries MUST include owner_id for multi-tenant isolation.
"""

from typing import Optional, Dict, Any, List
from rag.retrieval.query import QueryFilters


class FilterBuilder:
    """
    Builds ChromaDB 'where' dictionary matching Chroma filter specifications.
    SECURITY: Enforces mandatory owner_id filtering to prevent cross-user data access.
    """

    @staticmethod
    def build_where_filter(
        owner_id: str,  # REQUIRED: User ID for tenant isolation (SEC-001 fix)
        paper_ids: Optional[List[str]] = None,
        filters: Optional[QueryFilters] = None,
    ) -> Dict[str, Any]:  # Never returns None - always includes owner_id
        """
        Build ChromaDB filter with MANDATORY owner isolation.
        
        Args:
            owner_id: REQUIRED user ID for multi-tenant security
            paper_ids: Optional paper IDs to filter within user's scope
            filters: Optional additional filters
            
        Returns:
            Dict with owner_id filter ALWAYS included
            
        Raises:
            ValueError: If owner_id is empty or invalid
        """
        if not owner_id or not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required and must be a non-empty string (SEC-001 security requirement)")
        
        clauses: List[Dict[str, Any]] = []

        # CRITICAL: Owner isolation MUST be first clause
        clauses.append({"owner_id": owner_id.strip()})

        # Target paper IDs (within owner's scope)
        all_paper_ids = []
        if paper_ids:
            all_paper_ids.extend(paper_ids)
        if filters and filters.paper_ids:
            all_paper_ids.extend(filters.paper_ids)

        # Deduplicate
        all_paper_ids = list(dict.fromkeys(all_paper_ids))

        if len(all_paper_ids) == 1:
            clauses.append({"paper_id": all_paper_ids[0]})
        elif len(all_paper_ids) > 1:
            clauses.append({"paper_id": {"$in": all_paper_ids}})

        if filters:
            # Document IDs
            if filters.document_ids:
                if len(filters.document_ids) == 1:
                    clauses.append({"document_id": filters.document_ids[0]})
                else:
                    clauses.append({"document_id": {"$in": filters.document_ids}})

            # Sections
            if filters.sections:
                if len(filters.sections) == 1:
                    clauses.append({"section": filters.sections[0]})
                else:
                    clauses.append({"section": {"$in": filters.sections}})

        # Always return an $and clause with owner_id as first condition
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
