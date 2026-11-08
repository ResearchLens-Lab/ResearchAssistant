from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from backend.app.core.dependencies import CurrentUser, DBSession, RAGGatewayDep
from backend.app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from backend.app.schemas.common import Page
from backend.app.services.chat_service import ChatService
from backend.app.services.conversation_service import ConversationService
from backend.app.utils.pagination import PageParams

router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a grounded question about selected papers",
    description=(
        "Validates paper access, persists the user message, queries the RAG "
        "boundary and persists the assistant answer with its sources. "
        "Returns 503 RAG_UNAVAILABLE when the RAG service cannot answer."
    ),
)
async def chat(
    payload: ChatRequest, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    return await ChatService(db, rag).send_message(current_user, payload)


@router.post("/chat/stream", summary="Stream authenticated research progress and final response")
async def chat_stream(
    payload: ChatRequest, current_user: CurrentUser, db: DBSession, rag: RAGGatewayDep
):
    async def body():
        async for frame in ChatService(db, rag).stream_message(current_user, payload):
            yield frame

    return StreamingResponse(body(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation(
    payload: ConversationCreate, current_user: CurrentUser, db: DBSession
):
    return await ConversationService(db).create(current_user, payload)


@router.get(
    "/conversations",
    response_model=Page[ConversationResponse],
    summary="List own conversations",
)
async def list_conversations(
    current_user: CurrentUser,
    db: DBSession,
    params: PageParams = Depends(),
    q: Optional[str] = Query(default=None, description="Filter conversations by title query"),
):
    return await ConversationService(db).list(current_user, params, query=q)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a conversation",
)
async def get_conversation(
    conversation_id: str, current_user: CurrentUser, db: DBSession
):
    return await ConversationService(db).get_owned(current_user, conversation_id)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation title or source scope",
)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    return await ConversationService(db).update(current_user, conversation_id, payload)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="List messages (assistant messages include their RAG sources)",
)
async def list_messages(
    conversation_id: str, current_user: CurrentUser, db: DBSession
):
    return await ConversationService(db).list_messages(current_user, conversation_id)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: str, current_user: CurrentUser, db: DBSession
):
    await ConversationService(db).delete(current_user, conversation_id)
