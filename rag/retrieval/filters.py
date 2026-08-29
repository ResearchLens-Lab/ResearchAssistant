"""
Constructs ChromaDB metadata filters from QueryFilters or paper_ids.
"""

from typing import Optional, Dict, Any, List
from rag.retrieval.query import QueryFilters


class FilterBuilder:
    """
    Builds ChromaDB 'where' dictionary matching Chroma filter specifications.
    """

    @staticmethod
    def build_where_filter(
        paper_ids: Optional[List[str]] = None,
        filters: Optional[QueryFilters] = None,
    ) -> Optional[Dict[str, Any]]:
        clauses: List[Dict[str, Any]] = []

        # Target paper IDs
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

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}
