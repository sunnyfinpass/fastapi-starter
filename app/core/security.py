import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_hasher = PasswordHash.recommended()  # argon2


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)


def hash_token(raw: str) -> str:
    """SHA-256 of an opaque token. We store only this, never the raw refresh token."""
    return hashlib.sha256(raw.encode()).hexdigest()


def password_fingerprint(hashed_password: str) -> str:
    """Embedded in reset tokens so they die as soon as the password changes (single-use)."""
    return hash_token(hashed_password)[:16]


# ---------- JWT helpers ----------
def _encode(claims: dict[str, Any], minutes: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=minutes)
    return jwt.encode({**claims, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def _decode(token: str, expected_type: str) -> dict[str, Any] | None:
    """Every JWT carries a `type`, so a reset/verify token can never be used as an access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == expected_type else None


# ---------- access token ----------
def create_access_token(subject: str) -> str:
    return _encode({"sub": subject, "type": "access"}, settings.access_token_expire_minutes)


def decode_access_token(token: str) -> str | None:
    payload = _decode(token, "access")
    return payload.get("sub") if payload else None


# ---------- refresh token (opaque, stored hashed in DB) ----------
def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token_for_client, hash_for_db)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


# ---------- password reset token ----------
def create_password_reset_token(user_id: int, hashed_password: str) -> str:
    claims = {"sub": str(user_id), "type": "reset", "fp": password_fingerprint(hashed_password)}
    return _encode(claims, settings.reset_token_expire_minutes)


def decode_password_reset_token(token: str) -> tuple[int, str] | None:
    payload = _decode(token, "reset")
    return (int(payload["sub"]), payload["fp"]) if payload else None


# ---------- email verification token ----------
def create_verification_token(user_id: int, email: str) -> str:
    claims = {"sub": str(user_id), "type": "verify", "email": email}
    return _encode(claims, settings.verify_token_expire_hours * 60)


def decode_verification_token(token: str) -> tuple[int, str] | None:
    payload = _decode(token, "verify")
    return (int(payload["sub"]), payload["email"]) if payload else None
