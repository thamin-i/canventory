"""Schemas for notification settings and responses."""

from pydantic import BaseModel


class EmailNotificationSettings(BaseModel):
    """Email notification settings schema."""

    email_notifications_enabled: bool


class EmailNotificationResponse(BaseModel):
    """Email notification response schema."""

    email_notifications_enabled: bool
    smtp_configured: bool
    email: str
