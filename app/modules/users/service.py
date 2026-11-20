from collections.abc import Sequence

from pydantic import BaseModel

from app.core.exceptions import NotFoundError
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import AdminUserUpdate, UserUpdate


class UserService:
    """Profile + admin user management. (Registration/login live in AuthService.)"""

    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def get(self, user_id: int) -> User | None:
        return await self.repo.get_by_id(user_id)

    async def list(self, skip: int, limit: int) -> Sequence[User]:
        return await self.repo.list(skip, limit)

    async def update_profile(self, user: User, data: UserUpdate) -> User:
        return await self._apply(user, data)

    async def admin_update(self, user_id: int, data: AdminUserUpdate) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return await self._apply(user, data)

    async def _apply(self, user: User, data: BaseModel) -> User:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        return await self.repo.save(user)
