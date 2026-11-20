"""Dependency injection wiring (FastAPI's version of NestJS providers/guards, Laravel's container/gates)."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.service import AuthService
from app.modules.users.models import Role, User
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------- services ----------
def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))


def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(UserRepository(session), RefreshTokenRepository(session))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# ---------- guards ----------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], service: UserServiceDep
) -> User:
    sub = decode_access_token(token)
    user = await service.get(int(sub)) if sub else None
    if not user or not user.is_active:
        raise UnauthorizedError("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_verified_user(user: CurrentUser) -> User:
    if not user.is_verified:
        raise ForbiddenError("Email not verified")
    return user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


def require_roles(*roles: Role):
    """Role guard factory, like NestJS @Roles('admin'). Usage: Depends(require_roles(Role.admin))."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("Insufficient permissions")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.admin))]
