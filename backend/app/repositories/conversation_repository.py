from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.conversation import Conversation
from backend.app.models.message import Message


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        user_id: str,
        title: Optional[str] = None,
        paper_ids: Optional[list[str]] = None,
    ) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, paper_ids=paper_ids)
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def get_by_id(self, conversation_id: str) -> Optional[Conversation]:
        return await self.db.get(Conversation, conversation_id)

    async def list_by_user(
        self, user_id: str, offset: int, limit: int
    ) -> tuple[list[Conversation], int]:
        base = select(Conversation).where(Conversation.user_id == user_id)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = await self.db.execute(
            base.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    async def delete(self, conversation: Conversation) -> None:
        await self.db.execute(
            delete(Message).where(Message.conversation_id == conversation.id)
        )
        await self.db.delete(conversation)
        await self.db.flush()
