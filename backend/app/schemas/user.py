"""Pydantic schemas for User domain."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Shared fields between create and response."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Payload for user registration."""

    password: str = Field(..., min_length=8, max_length=72)
    role: UserRole = UserRole.VIEWER


class UserLogin(BaseModel):
    """Payload for login."""

    email: EmailStr
    password: str


class UserResponse(UserBase):
    """User data returned from the API (never includes password)."""

    id: int
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str  # user email
    exp: int
