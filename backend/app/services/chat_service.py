"""Chat orchestration: authenticate → validate access → persist → RAG → persist.

The backend never invents answers or citations; everything grounded comes from
the RAG boundary, and its source metadata is persisted verbatim."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.base import utcnow
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.message import MessageRole
from backend.app.models.user import User
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.message_repository import MessageRepository
from backend.app.schemas.chat import ChatRequest
from backend.app.services.conversation_service import ConversationService
from backend.app.services.paper_service import PaperService

logger = logging.getLogger("backend.chat")

_TITLE_MAX = 80


class ChatService:
    def __init__(self, db: AsyncSession, rag: RAGGateway):
        self.db = db
        self.rag = rag
        self.paper_service = PaperService(db)
        self.conversation_service = ConversationService(db)
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)

    async def send_message(self, user: User, payload: ChatRequest) -> dict[str, Any]:
        logger.info("chat request started user_id=%s", user.id)
        papers = await self.paper_service.validate_owned_papers(user, payload.paper_ids)
        paper_ids = [paper.id for paper in papers]

        if payload.conversation_id:
            conversation = await self.conversation_service.get_owned(
                user, payload.conversation_id
            )
        else:
            title = payload.question.strip()
            if len(title) > _TITLE_MAX:
                title = title[: _TITLE_MAX - 3] + "..."
            conversation = await self.conversations.create(
                user_id=user.id, title=title, paper_ids=paper_ids
            )

        await self.messages.create(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.question,
        )

        # A RAG failure raises before the commit below, so the failed request
        # persists nothing and the client receives a structured 503.
        result = await self.rag.ask_question(
            question=payload.question, paper_ids=paper_ids
        )

        answer = result.get("answer", "")
        sources = result.get("sources") or []
        assistant_message = await self.messages.create(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT.value,
            content=answer,
            sources=sources,
            meta={"paper_ids": result.get("paper_ids", paper_ids)},
        )
        conversation.updated_at = utcnow()
        await self.db.commit()
        return {
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "answer": answer,
            "sources": sources,
            "paper_ids": paper_ids,
        }
