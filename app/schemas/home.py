"""Pydantic schemas for home request/response validation."""

import typing as t
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.models import HomeMemberRole, HomeMembershipStatus


class HomeBase(BaseModel):
    """Base home schema."""

    name: str = Field(..., min_length=1, max_length=100)


class HomeCreate(HomeBase):
    """Schema for creating a new home."""


class HomeUpdate(BaseModel):
    """Schema for updating a home."""

    name: str | None = Field(None, min_length=1, max_length=100)


class HomeMemberResponse(BaseModel):
    """Schema for home member response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    email: str
    role: HomeMemberRole
    status: HomeMembershipStatus
    invited_at: datetime
    joined_at: datetime | None = None


class HomeResponse(HomeBase):
    """Schema for home response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    owner_username: str
    member_count: int
    item_count: int
    created_at: datetime
    updated_at: datetime


class HomeDetailResponse(HomeResponse):
    """Schema for detailed home response including members."""

    members: t.List[HomeMemberResponse]


class HomeListResponse(BaseModel):
    """Schema for home list response."""

    homes: t.List[HomeResponse]
    total: int


class HomeInviteRequest(BaseModel):
    """Schema for inviting a user to a home."""

    username_or_email: str = Field(..., min_length=1, max_length=255)


class HomeSwitchRequest(BaseModel):
    """Schema for switching current home."""

    home_id: int


class HomeSimple(BaseModel):
    """Simplified home schema for dropdowns."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_owner: bool


class PendingInvitationResponse(BaseModel):
    """Schema for pending invitation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int  # membership id
    home_id: int
    home_name: str
    owner_username: str
    invited_at: datetime
