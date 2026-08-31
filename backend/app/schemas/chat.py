from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.citation import Source


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    paper_ids: list[str] = Field(min_length=1)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[Source]
    paper_ids: list[str]


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    paper_ids: Optional[list[str]] = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    paper_ids: Optional[list[str]] = None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    sources: Optional[list[Source]] = None
    created_at: datetime
