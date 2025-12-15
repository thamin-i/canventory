"""Email notification API endpoints."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.config import SETTINGS
from app.core.database import get_db
from app.core.models import User
from app.schemas.notifications import (
    EmailNotificationResponse,
    EmailNotificationSettings,
)
from app.services.email_notifications import send_test_email

ROUTER = APIRouter(prefix="/notifications", tags=["Notifications"])


@ROUTER.get("/email/settings", response_model=EmailNotificationResponse)
async def get_email_notification_settings(
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> EmailNotificationResponse:
    """Get current email notification settings.

    Args:
        current_user (User): The currently authenticated user.

    Returns:
        EmailNotificationResponse: The email notification settings.
    """
    return EmailNotificationResponse(
        email_notifications_enabled=current_user.email_notifications_enabled,
        smtp_configured=SETTINGS.smtp_enabled,
        email=current_user.email,
    )


@ROUTER.put("/email/settings", response_model=EmailNotificationResponse)
async def update_email_notification_settings(
    email_settings: EmailNotificationSettings,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> EmailNotificationResponse:
    """Update email notification settings.

    Args:
        email_settings (EmailNotificationSettings):
            The new email notification settings.
        db (AsyncSession):
            The database session.
        current_user (User):
            The currently authenticated user.

    Returns:
        EmailNotificationResponse: The updated email notification settings.
    """
    if email_settings.email_notifications_enabled and not SETTINGS.smtp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Email notifications cannot be enabled."
                " SMTP is not configured."
            ),
        )

    current_user.email_notifications_enabled = (
        email_settings.email_notifications_enabled
    )
    await db.flush()

    return EmailNotificationResponse(
        email_notifications_enabled=current_user.email_notifications_enabled,
        smtp_configured=SETTINGS.smtp_enabled,
        email=current_user.email,
    )


@ROUTER.post("/email/test")
async def send_test_email_notification(
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> t.Dict[str, t.Any]:
    """Send a test email to verify email notifications are working.

    Args:
        current_user (User):
            The currently authenticated user.

    Returns:
        Dict[str, Any]: A dictionary indicating success or failure.
    """
    if not SETTINGS.smtp_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email notifications not configured. SMTP is not enabled.",
        )

    if not current_user.email_notifications_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Email notifications not enabled "
                "for your account. Enable them first."
            ),
        )

    if await send_test_email(current_user):
        return {"success": True, "message": "Test email sent successfully"}

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to send test email. Check server configuration.",
    )
