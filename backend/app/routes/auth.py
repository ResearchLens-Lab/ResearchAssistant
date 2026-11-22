from typing import Optional
from fastapi import APIRouter, Header, Response, status

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    LocalSessionRequest,
)
from backend.app.schemas.user import UserResponse
from backend.app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(payload: RegisterRequest, db: DBSession):
    return await AuthService(db).register(payload)


@router.post("/login", response_model=LoginResponse, summary="Login with username or legacy email/password")
async def login(payload: LoginRequest, db: DBSession):
    return await AuthService(db).login(payload)


@router.get("/me", response_model=UserResponse, summary="Current authenticated user")
async def me(current_user: CurrentUser):
    return current_user


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair (rotation)",
)
async def refresh(payload: RefreshRequest, db: DBSession):
    return await AuthService(db).refresh(payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token",
)
async def logout(payload: LogoutRequest, db: DBSession):
    await AuthService(db).logout(payload.refresh_token)


@router.post(
    "/local-session",
    response_model=LoginResponse,
    summary="Establish local session for desktop runtime without credentials",
)
async def local_session(
    response: Response,
    db: DBSession,
    payload: Optional[LocalSessionRequest] = None,
    desktop_key: Optional[str] = Header(None, alias="X-ResearchLens-Desktop-Key"),
):
    key = (payload.request_key if payload else None) or desktop_key or ""
    return await AuthService(db).create_local_session(key, response)
