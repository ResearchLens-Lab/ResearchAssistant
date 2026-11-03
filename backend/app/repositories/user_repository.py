from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> Optional[User]:
        # Keep email login for existing accounts while making username the primary path.
        normalized = identifier.strip().lower()
        result = await self.db.execute(
            select(User).where((User.username == normalized) | (User.email == normalized))
        )
        return result.scalar_one_or_none()

    async def create(
        self, *, email: str, username: str, hashed_password: str, full_name: Optional[str]
    ) -> User:
        user = User(email=email, username=username, hashed_password=hashed_password, full_name=full_name)
        self.db.add(user)
        await self.db.flush()
        return user
