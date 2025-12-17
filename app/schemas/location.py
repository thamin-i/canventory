"""Pydantic schemas for storage location request/response validation."""

import typing as t
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    """Base location schema."""

    name: str = Field(..., min_length=1, max_length=100)


class LocationCreate(LocationBase):
    """Schema for creating a new storage location."""


class LocationResponse(LocationBase):
    """Schema for storage location response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class LocationListResponse(BaseModel):
    """Schema for storage location list response."""

    locations: t.List[LocationResponse]
    total: int
