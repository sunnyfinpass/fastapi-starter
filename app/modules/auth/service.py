from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.exceptions import AppError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_verification_token,
    decode_password_reset_token,
    decode_verification_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_fingerprint,
    verify_password,
)
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.schemas import TokenPair
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; Postgres returns aware ones. Normalise."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AuthService:
    """All authentication business rules. No FastAPI imports, so it's easy to unit test."""

    def __init__(self, users: UserRepository, tokens: RefreshTokenRepository) -> None:
        self.users = users
        self.tokens = tokens

    # ---------- register / login ----------
    async def register(self, data: UserCreate) -> tuple[User, str]:
        email = data.email.lower()
        if await self.users.get_by_email(email):
            raise ConflictError("Email already registered")
        user = await self.users.create(email, hash_password(data.password), data.full_name)
        return user, create_verification_token(user.id, user.email)

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.users.get_by_email(email.lower())
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is disabled")
        return await self._issue_tokens(user)

    # ---------- refresh / logout ----------
    async def refresh(self, raw_token: str) -> TokenPair:
        invalid = UnauthorizedError("Invalid or expired refresh token")
        stored = await self.tokens.get_by_hash(hash_token(raw_token))
        if not stored:
            raise invalid
        if stored.revoked_at is not None:
            # A rotated/revoked token was replayed -> likely stolen. Kill every session.
            await self.tokens.revoke_all_for_user(stored.user_id)
            raise invalid
        if _aware(stored.expires_at) < datetime.now(UTC):
            raise invalid
        user = await self.users.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise invalid
        await self.tokens.revoke(stored)  # rotation: each refresh token works once
        return await self._issue_tokens(user)

    async def logout(self, raw_token: str) -> None:
        stored = await self.tokens.get_by_hash(hash_token(raw_token))
        if stored and stored.revoked_at is None:
            await self.tokens.revoke(stored)

    async def logout_all(self, user: User) -> None:
        await self.tokens.revoke_all_for_user(user.id)

    # ---------- passwords ----------
    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.hashed_password):
            raise AppError("Current password is incorrect")
        user.hashed_password = hash_password(new)
        await self.users.save(user)
        await self.tokens.revoke_all_for_user(user.id)  # sign out everywhere

    async def request_password_reset(self, email: str) -> str | None:
        """Returns a token, or None for unknown email (caller must not reveal which)."""
        user = await self.users.get_by_email(email.lower())
        if not user or not user.is_active:
            return None
        return create_password_reset_token(user.id, user.hashed_password)

    async def reset_password(self, token: str, new_password: str) -> None:
        invalid = UnauthorizedError("Invalid or expired reset token")
        decoded = decode_password_reset_token(token)
        if not decoded:
            raise invalid
        user_id, fingerprint = decoded
        user = await self.users.get_by_id(user_id)
        if not user or password_fingerprint(user.hashed_password) != fingerprint:
            raise invalid  # unknown user, or token already used
        user.hashed_password = hash_password(new_password)
        await self.users.save(user)
        await self.tokens.revoke_all_for_user(user.id)

    # ---------- email verification ----------
    def create_verification_token_for(self, user: User) -> str:
        if user.is_verified:
            raise AppError("Email already verified")
        return create_verification_token(user.id, user.email)

    async def verify_email(self, token: str) -> None:
        invalid = AppError("Invalid or expired verification token")
        decoded = decode_verification_token(token)
        if not decoded:
            raise invalid
        user_id, email = decoded
        user = await self.users.get_by_id(user_id)
        if not user or user.email != email:
            raise invalid
        if not user.is_verified:
            user.is_verified = True
            await self.users.save(user)

    # ---------- internals ----------
    async def _issue_tokens(self, user: User) -> TokenPair:
        raw, hashed = generate_refresh_token()
        expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        await self.tokens.add(user.id, hashed, expires)
        return TokenPair(
            access_token=create_access_token(str(user.id)),
            refresh_token=raw,
            expires_in=settings.access_token_expire_minutes * 60,
        )
