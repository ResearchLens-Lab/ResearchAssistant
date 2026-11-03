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
        conv = await self.db.get(Conversation, conversation_id)
        if conv:
            count = (
                await self.db.execute(
                    select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
                )
            ).scalar() or 0
            conv.message_count = count
        return conv

    async def list_by_user(
        self, user_id: str, offset: int, limit: int, query: Optional[str] = None
    ) -> tuple[list[Conversation], int]:
        base = select(Conversation).where(Conversation.user_id == user_id)
        if query and query.strip():
            base = base.where(Conversation.title.ilike(f"%{query.strip()}%"))
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()

        msg_counts = (
            select(Message.conversation_id, func.count(Message.id).label("cnt"))
            .group_by(Message.conversation_id)
            .subquery()
        )
        stmt = (
            select(Conversation, func.coalesce(msg_counts.c.cnt, 0).label("message_count"))
            .outerjoin(msg_counts, Conversation.id == msg_counts.c.conversation_id)
            .where(Conversation.user_id == user_id)
        )
        if query and query.strip():
            stmt = stmt.where(Conversation.title.ilike(f"%{query.strip()}%"))

        rows = await self.db.execute(
            stmt.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit)
        )
        results = []
        for conv, count in rows.all():
            conv.message_count = count
            results.append(conv)
        return results, total

    async def update(
        self,
        conversation: Conversation,
        *,
        title: Optional[str] = None,
        paper_ids: Optional[list[str]] = None,
    ) -> Conversation:
        if title is not None:
            conversation.title = title
        if paper_ids is not None:
            conversation.paper_ids = paper_ids
        self.db.add(conversation)
        await self.db.flush()
        return conversation

    async def delete(self, conversation: Conversation) -> None:
        await self.db.execute(
            delete(Message).where(Message.conversation_id == conversation.id)
        )
        await self.db.delete(conversation)
        await self.db.flush()
