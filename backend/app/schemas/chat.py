from datetime import datetime
from typing import Optional, Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.citation import Source


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    paper_ids: list[str] = Field(min_length=1)
    document_ids: Optional[list[str]] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    answer_mode: Literal["EVIDENCE_FIRST", "DOCUMENTS_GENERAL", "OPTIONAL_LOCAL_AI", "DOCUMENTS_ONLY", "INDEPENDENT"] = "EVIDENCE_FIRST"


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[Source]
    paper_ids: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatStreamEvent(BaseModel):
    event_id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_token_payload(self):
        if self.type == "token" and (not isinstance(self.data.get("text"), str) or self.data.get("provisional") is not True):
            raise ValueError("Token events must contain provisional text.")
        return self


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    paper_ids: Optional[list[str]] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    paper_ids: Optional[list[str]] = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    paper_ids: Optional[list[str]] = None
    message_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: str
    content: str
    sources: Optional[list[Source]] = None
    meta: Optional[dict[str, Any]] = None
    created_at: datetime
