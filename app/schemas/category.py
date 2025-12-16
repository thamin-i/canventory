"""Pydantic schemas for category request/response validation."""

import typing as t
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    """Base category schema."""

    label: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(..., min_length=1, max_length=10)
    sort_order: int = Field(0, ge=0)


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""

    value: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z_]+$")


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    label: str | None = Field(None, min_length=1, max_length=100)
    icon: str | None = Field(None, min_length=1, max_length=10)
    sort_order: int | None = Field(None, ge=0)


class CategoryResponse(CategoryBase):
    """Schema for category response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    value: str
    created_at: datetime


class CategoryListResponse(BaseModel):
    """Schema for category list response."""

    categories: t.List[CategoryResponse]
    total: int
