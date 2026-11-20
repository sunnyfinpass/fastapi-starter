from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, UserServiceDep
from app.modules.users.schemas import AdminUserUpdate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdate, current_user: CurrentUser, service: UserServiceDep):
    return await service.update_profile(current_user, data)


@router.get("", response_model=list[UserRead])
async def list_users(
    _: AdminUser,
    service: UserServiceDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await service.list(skip, limit)


@router.patch("/{user_id}", response_model=UserRead)
async def admin_update_user(
    user_id: int, data: AdminUserUpdate, _: AdminUser, service: UserServiceDep
):
    return await service.admin_update(user_id, data)
