"""Chat orchestration: authenticate → validate access → persist → RAG → persist.

The backend never invents answers or citations; everything grounded comes from
the RAG boundary, and its source metadata is persisted verbatim."""

import logging
import inspect
import asyncio
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.base import utcnow
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.message import MessageRole
from backend.app.models.user import User
from backend.app.repositories.conversation_repository import ConversationRepository
from backend.app.repositories.message_repository import MessageRepository
from backend.app.schemas.chat import ChatRequest, ChatStreamEvent
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

    async def send_message(self, user: User, payload: ChatRequest, progress_callback=None) -> dict[str, Any]:
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

        prior_messages = await self.messages.list_by_conversation(conversation.id)
        user_message = await self.messages.create(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.question,
        )
        latest_time = max((m.created_at for m in prior_messages), default=None)
        if latest_time and user_message.created_at <= latest_time:
            user_message.created_at = latest_time + timedelta(microseconds=1)

        # Keep recent turns for reference resolution. They are passed as a hint
        # to deterministic query planning; only retrieved passages are evidence.
        prior_turns = prior_messages[-6:]
        conversation_context = "\n".join(
            f"{message.role}: {message.content[:1200]}" for message in prior_turns
        ) or None

        # A RAG failure raises before the commit below, so the failed request
        # persists nothing and the client receives a structured 503.
        rag_kwargs = {"question": payload.question, "paper_ids": paper_ids}
        if "user_id" in inspect.signature(self.rag.ask_question).parameters:
            rag_kwargs["user_id"] = str(user.id)
        if conversation_context and "conversation_context" in inspect.signature(self.rag.ask_question).parameters:
            rag_kwargs["conversation_context"] = conversation_context
        if progress_callback and "progress_callback" in inspect.signature(self.rag.ask_question).parameters:
            rag_kwargs["progress_callback"] = progress_callback
        result = await self.rag.ask_question(**rag_kwargs)
        if progress_callback and getattr(progress_callback, "is_cancelled", lambda: False)():
            raise asyncio.CancelledError()

        answer = result.get("answer", "")
        sources = result.get("sources") or []
        assistant_message = await self.messages.create(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT.value,
            content=answer,
            sources=sources,
            meta={"paper_ids": result.get("paper_ids", paper_ids),
                  "research": result.get("metadata", {}).get("research", {}),
                  "answer_mode": result.get("metadata", {}).get("answer_mode", "unknown"),
                  "generation_reason": result.get("metadata", {}).get("generation_reason"),
                  "generation_provider": result.get("metadata", {}).get("generation_provider"),
                  "cache_hit": result.get("metadata", {}).get("cache_hit", False),
                  "model_calls": result.get("metadata", {}).get("model_calls", 0),
                  "llm_usage": result.get("metadata", {}).get("llm_usage", {"measured": [], "estimated": False})},
        )
        assistant_message.created_at = user_message.created_at + timedelta(microseconds=1)
        conversation.updated_at = utcnow()
        await self.db.commit()
        return {
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "answer": answer,
            "sources": sources,
            "paper_ids": paper_ids,
            "metadata": result.get("metadata", {}),
        }

    async def stream_message(self, user: User, payload: ChatRequest):
        """Yield authenticated progress, provisional provider tokens, and persisted completion."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        request_id = str(uuid.uuid4())
        allowed_events = {"retrieval_started", "sources_found", "additional_retrieval", "evidence_ready",
                          "generation_skipped", "generation_started", "verification_started", "verification_completed", "planning_completed", "token"}
        cancelled = asyncio.Event()

        def event(event_type: str, data: dict[str, Any] | None = None):
            item = ChatStreamEvent(event_id=request_id, type=event_type, data=data or {})
            return f"id: {item.event_id}\nevent: {item.type}\ndata: {item.model_dump_json()}\n\n"

        def callback(value: dict[str, Any]):
            if cancelled.is_set():
                return
            loop.call_soon_threadsafe(queue.put_nowait, value)
        callback.is_cancelled = cancelled.is_set

        yield event("started", {})
        yield event("planning_started", {})
        task = asyncio.create_task(self.send_message(user, payload, progress_callback=callback))
        try:
            while not task.done():
                try:
                    value = await asyncio.wait_for(queue.get(), timeout=0.2)
                    kind = value.get("type")
                    if kind in allowed_events:
                        yield event(kind, {k: v for k, v in value.items() if k != "type"})
                except asyncio.TimeoutError:
                    continue
            # Drain callbacks queued immediately before completion.
            while not queue.empty():
                value = queue.get_nowait()
                kind = value.get("type")
                if kind in allowed_events:
                    yield event(kind, {k: v for k, v in value.items() if k != "type"})
            result = await task
            yield event("completed", result)
        except asyncio.CancelledError:
            cancelled.set()
            task.cancel()
            raise
        except Exception as exc:
            logger.error("chat stream failed request_id=%s exception_type=%s", request_id, type(exc).__name__)
            yield event("error", {"message": "The research request could not be completed."})
