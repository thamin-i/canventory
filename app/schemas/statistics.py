"""Pydantic schemas for request/response validation."""

import typing as t

from pydantic import BaseModel


class CanventoryStats(BaseModel):
    """Schema for food closet statistics."""

    total_items: int
    total_quantity: int
    items_by_category: t.Dict[str, int]
    expiration_summary: t.Dict[str, int]
    items_expiring_soon: int
