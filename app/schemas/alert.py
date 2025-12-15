"""Pydantic schemas for request/response validation."""

import typing as t
from datetime import datetime

from pydantic import BaseModel

from app.core.models import ExpirationStatus, FoodCategory


class ExpirationAlert(BaseModel):
    """Schema for expiration alert."""

    item_id: int
    item_name: str
    expiration_date: datetime
    days_until_expiration: int
    status: ExpirationStatus
    quantity: int
    category: FoodCategory


class ExpirationAlertSummary(BaseModel):
    """Schema for expiration alert summary."""

    expired_count: int
    critical_count: int
    warning_count: int
    expired_items: t.List[ExpirationAlert]
    critical_items: t.List[ExpirationAlert]
    warning_items: t.List[ExpirationAlert]
