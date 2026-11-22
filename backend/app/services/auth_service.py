import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.core.exceptions import (
    EmailAlreadyRegisteredError,
    UsernameAlreadyTakenError,
    UnauthorizedError,
)
from backend.app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.app.models.user import User
from backend.app.repositories.refresh_token_repository import RefreshTokenRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, TokenResponse
from backend.app.schemas.user import UserResponse

logger = logging.getLogger("backend.auth")

# In-memory grace window for rotated refresh tokens (30s TTL)
_ROTATED_TOKEN_GRACE: Dict[str, Tuple[TokenResponse, float]] = {}


def _cleanup_grace_window() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _ROTATED_TOKEN_GRACE.items() if exp < now]
    for k in expired:
        _ROTATED_TOKEN_GRACE.pop(k, None)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    async def register(self, payload: RegisterRequest) -> User:
        email = payload.email.lower()
        if await self.users.get_by_email(email):
            raise EmailAlreadyRegisteredError()
        if await self.users.get_by_username(payload.username):
            raise UsernameAlreadyTakenError()
        try:
            user = await self.users.create(
                email=email,
                username=payload.username,
                hashed_password=hash_password(payload.password),
                full_name=payload.full_name,
            )
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # Database constraints remain authoritative under concurrent registrations.
            if await self.users.get_by_username(payload.username):
                raise UsernameAlreadyTakenError() from exc
            if await self.users.get_by_email(email):
                raise EmailAlreadyRegisteredError() from exc
            raise
        logger.info("user registered user_id=%s", user.id)
        return user

    async def login(self, payload: LoginRequest) -> LoginResponse:
        user = await self.users.get_by_identifier(payload.identifier)
        if not user or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedError("The username or password is incorrect.")
        if not user.is_active:
            raise UnauthorizedError("The username or password is incorrect.")
        tokens = await self._issue_tokens(user.id)
        await self.db.commit()
        logger.info("user authenticated user_id=%s", user.id)
        return LoginResponse(**tokens.model_dump(), user=UserResponse.model_validate(user))

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        jti = payload.get("jti")
        user_id = payload["sub"]
        row = await self.refresh_tokens.get(jti) if jti else None
        if row is None or row.user_id != user_id:
            raise UnauthorizedError("Invalid refresh token.")
        if row.revoked:
            is_desktop = os.environ.get("DESKTOP_RUNTIME", "").lower() in ("true", "1")
            if is_desktop:
                _cleanup_grace_window()
                if jti and jti in _ROTATED_TOKEN_GRACE:
                    cached_tokens, exp = _ROTATED_TOKEN_GRACE[jti]
                    if time.time() < exp:
                        logger.info("Serving refresh token from 30s grace window user_id=%s jti=%s", user_id, jti)
                        return cached_tokens
                logger.warning("Revoked token presented in desktop runtime; skipping blanket family revocation user_id=%s", user_id)
            else:
                # Reuse outside grace window suggests theft: revoke the whole family.
                await self.refresh_tokens.revoke_all_for_user(user_id)
                await self.db.commit()
                logger.warning("refresh token reuse detected user_id=%s", user_id)
            raise UnauthorizedError("Refresh token has been revoked.")

        if _as_naive_utc(row.expires_at) < datetime.utcnow():
            raise UnauthorizedError("Refresh token has expired.")
        user = await self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User is not active.")
        await self.refresh_tokens.revoke(row)  # rotation
        tokens = await self._issue_tokens(user_id)
        if jti:
            _ROTATED_TOKEN_GRACE[jti] = (tokens, time.time() + 30.0)
        await self.db.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        except UnauthorizedError:
            return  # already invalid/expired; logout is idempotent
        jti = payload.get("jti")
        row = await self.refresh_tokens.get(jti) if jti else None
        if row and not row.revoked:
            await self.refresh_tokens.revoke(row)
            await self.db.commit()

    async def create_local_session(
        self, request_key: str, response: Optional[Any] = None
    ) -> LoginResponse:
        settings = get_settings()
        expected_key = settings.desktop_request_key
        if expected_key and request_key != expected_key:
            raise UnauthorizedError("Invalid desktop request key.")

        result = await self.db.execute(
            select(User).where(User.is_active == True).order_by(User.created_at.asc())
        )
        user = result.scalars().first()

        if not user:
            import secrets
            user = await self.users.create(
                email="researcher@local.researchlens",
                username="researcher",
                full_name="Researcher",
                hashed_password=hash_password(secrets.token_urlsafe(24)),
            )

        tokens = await self._issue_tokens(user.id)
        await self.db.commit()

        if response is not None and hasattr(response, "set_cookie"):
            response.set_cookie(
                key="access_token",
                value=tokens.access_token,
                httponly=True,
                samesite="lax",
                max_age=settings.access_token_expire_minutes * 60,
            )

        logger.info("local session established user_id=%s", user.id)
        return LoginResponse(**tokens.model_dump(), user=UserResponse.model_validate(user))

    async def _issue_tokens(self, user_id: str) -> TokenResponse:
        access = create_access_token(user_id)
        refresh, jti, expires_at = create_refresh_token(user_id)
        await self.refresh_tokens.create(jti=jti, user_id=user_id, expires_at=expires_at)
        settings = get_settings()
        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )
