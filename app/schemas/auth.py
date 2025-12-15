"""Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """JWT token payload data."""

    username: str | None = None
    user_id: int | None = None


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, max_length=100)


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime


class RegistrationResult(BaseModel):
    """Result of user registration."""

    user: UserResponse


class LoginResult(BaseModel):
    """Result of user login."""

    token: Token
    user: UserResponse


class PasswordChange(BaseModel):
    """Schema for password change request."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordChangeResult(BaseModel):
    """Result of password change operation."""

    success: bool
    message: str


class EmailChange(BaseModel):
    """Schema for email change request."""

    new_email: EmailStr
    password: str = Field(..., min_length=1)


class EmailChangeResult(BaseModel):
    """Result of email change operation."""

    success: bool
    message: str
    new_email: str | None = None
