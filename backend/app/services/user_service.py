from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User
from backend.app.schemas.user import UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_profile(self, user: User, payload: UserUpdate) -> User:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        await self.db.flush()
        await self.db.commit()
        return user
