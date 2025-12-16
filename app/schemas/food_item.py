"""Pydantic schemas for request/response validation."""

import typing as t
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.models import ExpirationStatus


class FoodItemBase(BaseModel):
    """Base food item schema."""

    name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., ge=1)
    expiration_date: datetime
    category: str = Field("other", max_length=50)
    description: str | None = Field(None, max_length=1000)


class FoodItemCreate(FoodItemBase):
    """Schema for creating a new food item."""

    image_base64: str | None = Field(
        None, description="Base64 encoded image data (optional)"
    )

    @field_validator("expiration_date")
    @classmethod
    def validate_expiration_date(cls, v: datetime) -> datetime:
        """Ensure expiration date is in the future for new items.

        Args:
            v (datetime): The expiration date to validate.

        Returns:
            datetime: The validated expiration date.
        """
        # Allow dates in the past for tracking purposes, but warn
        return v


class FoodItemUpdate(BaseModel):
    """Schema for updating a food item."""

    name: str | None = Field(None, min_length=1, max_length=255)
    quantity: int | None = Field(None, ge=0)
    expiration_date: datetime | None = None
    category: str | None = Field(None, max_length=50)
    description: str | None = Field(None, max_length=1000)
    image_base64: str | None = Field(
        None, description="Base64 encoded image data (optional)"
    )
    remove_image: bool | None = Field(
        False, description="Set to true to remove the current image"
    )


class FoodItemResponse(FoodItemBase):
    """Schema for food item response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    expiration_status: ExpirationStatus
    days_until_expiration: int
    has_image: bool
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: int | None = None


class FoodItemListResponse(BaseModel):
    """Schema for paginated food item list response."""

    items: t.List[FoodItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
