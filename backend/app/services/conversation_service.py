# Deferred annotations: the `list` method below must not shadow builtin
# `list` in signature annotations.
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import NotFoundError
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.user import User
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.message_repository import MessageRepository
from backend.app.schemas.chat import ConversationCreate
from backend.app.services.paper_service import PaperService
from backend.app.utils.pagination import PageParams, page_payload


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)

    async def create(self, user: User, payload: ConversationCreate) -> Conversation:
        if payload.paper_ids:
            await PaperService(self.db).validate_owned_papers(user, payload.paper_ids)
        conversation = await self.conversations.create(
            user_id=user.id, title=payload.title, paper_ids=payload.paper_ids
        )
        await self.db.commit()
        return conversation

    async def get_owned(self, user: User, conversation_id: str) -> Conversation:
        conversation = await self.conversations.get_by_id(conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise NotFoundError("Conversation was not found.")
        return conversation

    async def list(self, user: User, params: PageParams) -> dict[str, Any]:
        items, total = await self.conversations.list_by_user(
            user.id, params.offset, params.page_size
        )
        return page_payload(items, total, params)

    async def list_messages(self, user: User, conversation_id: str) -> list[Message]:
        await self.get_owned(user, conversation_id)
        return await self.messages.list_by_conversation(conversation_id)

    async def delete(self, user: User, conversation_id: str) -> None:
        conversation = await self.get_owned(user, conversation_id)
        await self.conversations.delete(conversation)
        await self.db.commit()
