from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.document import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        paper_id: str,
        filename: str,
        storage_path: str,
        content_type: str,
        file_size: int,
    ) -> Document:
        document = Document(
            paper_id=paper_id,
            filename=filename,
            storage_path=storage_path,
            content_type=content_type,
            file_size=file_size,
        )
        self.db.add(document)
        await self.db.flush()
        return document

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        return await self.db.get(Document, document_id)

    async def list_by_paper(self, paper_id: str) -> list[Document]:
        rows = await self.db.execute(
            select(Document)
            .where(Document.paper_id == paper_id)
            .order_by(Document.created_at.desc())
        )
        return list(rows.scalars().all())
