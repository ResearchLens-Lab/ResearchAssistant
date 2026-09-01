from fastapi import APIRouter

from backend.app.core.dependencies import CurrentUser, DBSession
from backend.app.schemas.user import UserResponse, UserUpdate
from backend.app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Get own profile")
async def get_profile(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserResponse, summary="Update own profile")
async def update_profile(payload: UserUpdate, current_user: CurrentUser, db: DBSession):
    return await UserService(db).update_profile(current_user, payload)
