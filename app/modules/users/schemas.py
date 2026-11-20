from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import Role


class UserCreate(BaseModel):  # like a NestJS DTO / Laravel FormRequest
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserRead(BaseModel):  # like a Laravel API Resource
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    role: Role
    is_active: bool
    is_verified: bool
    created_at: datetime
