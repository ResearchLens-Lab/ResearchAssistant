from datetime import datetime
from typing import Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, *, jti: str, user_id: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(id=jti, user_id=user_id, expires_at=expires_at)
        self.db.add(token)
        await self.db.flush()
        return token

    async def get(self, jti: str) -> Optional[RefreshToken]:
        return await self.db.get(RefreshToken, jti)

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True)
        )
