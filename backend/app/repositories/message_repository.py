from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.message import Message


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        sources: Optional[list[dict[str, Any]]] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=sources,
            meta=meta,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_by_conversation(self, conversation_id: str) -> list[Message]:
        rows = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(rows.scalars().all())
