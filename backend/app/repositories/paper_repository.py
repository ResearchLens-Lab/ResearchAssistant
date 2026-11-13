from typing import Any, Optional

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document
from backend.app.models.paper import Paper


class PaperRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, owner_id: str, data: dict[str, Any]) -> Paper:
        paper = Paper(owner_id=owner_id, **data)
        self.db.add(paper)
        await self.db.flush()
        return paper

    async def get_by_id(self, paper_id: str) -> Optional[Paper]:
        return await self.db.get(Paper, paper_id)

    async def list_by_owner(
        self, owner_id: str, offset: int, limit: int
    ) -> tuple[list[Paper], int]:
        base = select(Paper).where(Paper.owner_id == owner_id)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = await self.db.execute(
            base.order_by(Paper.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    async def search(
        self,
        owner_id: str,
        q: Optional[str],
        author: Optional[str],
        year: Optional[int],
        offset: int,
        limit: int,
    ) -> tuple[list[Paper], int]:
        stmt = select(Paper).where(Paper.owner_id == owner_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Paper.title.ilike(like),
                    Paper.description.ilike(like),
                    Paper.abstract.ilike(like),
                )
            )
        if author:
            stmt = stmt.where(cast(Paper.authors, String).ilike(f"%{author}%"))
        if year is not None:
            stmt = stmt.where(Paper.publication_year == year)
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = await self.db.execute(
            stmt.order_by(Paper.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    async def update(self, paper: Paper, data: dict[str, Any]) -> Paper:
        for key, value in data.items():
            setattr(paper, key, value)
        await self.db.flush()
        return paper

    async def delete(self, paper: Paper) -> None:
        # Documents are removed explicitly so deletion does not depend on
        # database-level cascade support.
        await self.db.execute(delete(Document).where(Document.paper_id == paper.id))
        await self.db.delete(paper)
        await self.db.flush()
