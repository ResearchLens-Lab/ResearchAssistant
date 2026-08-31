from typing import Any, Sequence

from fastapi import Query


class PageParams:
    """Common `page`/`page_size` query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-based page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_payload(items: Sequence[Any], total: int, params: PageParams) -> dict[str, Any]:
    total_pages = (total + params.page_size - 1) // params.page_size if total else 0
    return {
        "items": list(items),
        "page": params.page,
        "page_size": params.page_size,
        "total": total,
        "total_pages": total_pages,
    }
