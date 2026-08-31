"""Shared FastAPI dependencies: database session, current user, integration clients."""

from typing import Annotated, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ForbiddenError, UnauthorizedError
from backend.app.core.security import ACCESS_TOKEN_TYPE, decode_token
from backend.app.database.session import get_db
from backend.app.integrations.knowledge_graph_client import (
    KnowledgeGraphClient,
    knowledge_graph_client,
)
from backend.app.integrations.rag_gateway import RAGGateway
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

DBSession = Annotated[AsyncSession, Depends(get_db)]

_rag_gateway: Optional[RAGGateway] = None


def get_rag_gateway() -> RAGGateway:
    global _rag_gateway
    if _rag_gateway is None:
        _rag_gateway = RAGGateway()
    return _rag_gateway


def get_knowledge_graph_client() -> KnowledgeGraphClient:
    return knowledge_graph_client


async def get_current_user(
    db: DBSession,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
) -> User:
    """Reads the Authorization header, validates the token, loads the user
    and verifies active status."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing authorization token.")
    payload = decode_token(credentials.credentials, expected_type=ACCESS_TOKEN_TYPE)
    user = await UserRepository(db).get_by_id(payload["sub"])
    if user is None:
        raise UnauthorizedError("User not found.")
    if not user.is_active:
        raise ForbiddenError("User account is inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
RAGGatewayDep = Annotated[RAGGateway, Depends(get_rag_gateway)]
KnowledgeGraphDep = Annotated[KnowledgeGraphClient, Depends(get_knowledge_graph_client)]
