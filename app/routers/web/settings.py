"""Web settings routes."""

import typing as t

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_web_user
from app.core.config import SETTINGS
from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import User
from app.services import (
    AuthService,
    EmailExistsError,
    InvalidCurrentPasswordError,
)
from app.services.email_notifications import send_test_email

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/settings", response_class=HTMLResponse, response_model=None)
async def settings_page(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Render user settings page.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        message (str | None): An optional success message to display.
        error (str | None): An optional error message to display.

    Returns:
        RedirectResponse | HTMLResponse:
            The rendered settings page or a redirect to login.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    return TEMPLATES.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            "user": user,
            "smtp_enabled": SETTINGS.smtp_enabled,
            "message": message,
            "error": error,
        },
    )


@ROUTER.post("/settings/notifications")
async def update_notification_settings(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Update email notification settings via JSON.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: The result of the update operation.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Not authenticated"},
        )

    try:
        body: t.Dict[str, t.Any] = await request.json()
        enabled: bool = body.get("enabled", False)
    except Exception:  # pylint: disable=broad-except
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid request"},
        )

    user.email_notifications_enabled = enabled
    await db.flush()

    status_msg: str = "enabled" if enabled else "disabled"
    return JSONResponse(
        content={
            "success": True,
            "message": f"Email notifications {status_msg}",
            "enabled": enabled,
        },
    )


@ROUTER.post("/settings/test-email")
async def test_email_endpoint(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Send a test email to verify email notifications are working.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: The result of the test email operation.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Not authenticated"},
        )

    if not SETTINGS.smtp_enabled:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Email notifications not configured",
            },
        )

    if not user.email_notifications_enabled:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Email notifications not enabled for your account",
            },
        )

    if await send_test_email(user):
        return JSONResponse(
            content={
                "success": True,
                "message": "Test email sent successfully",
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": (
                "Failed to send test email." " Check server configuration."
            ),
        },
    )


@ROUTER.post("/settings/change-password")
async def change_password_endpoint(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Change the current user's password via JSON.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: The result of the password change operation.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Not authenticated"},
        )

    try:
        body: t.Dict[str, t.Any] = await request.json()
        current_password: str = body.get("current_password", "")
        new_password: str = body.get("new_password", "")
    except Exception:  # pylint: disable=broad-except
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid request"},
        )

    if not current_password or not new_password:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Both current and new password are required",
            },
        )

    if len(new_password) < 8:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "New password must be at least 8 characters",
            },
        )

    try:
        await AuthService(db).change_password(
            user=user,
            current_password=current_password,
            new_password=new_password,
        )
        return JSONResponse(
            content={
                "success": True,
                "message": "Password changed successfully",
            },
        )
    except InvalidCurrentPasswordError:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Current password is incorrect",
            },
        )


@ROUTER.post("/settings/change-email")
async def change_email_endpoint(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Change the current user's email via JSON.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: The result of the email change operation.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Not authenticated"},
        )

    try:
        body: t.Dict[str, t.Any] = await request.json()
        new_email: str = body.get("new_email", "")
        password: str = body.get("password", "")
    except Exception:  # pylint: disable=broad-except
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid request"},
        )

    if not new_email or not password:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Email and password are required",
            },
        )

    try:
        updated_email: str = await AuthService(db).change_email(
            user=user,
            new_email=new_email,
            password=password,
        )
        return JSONResponse(
            content={
                "success": True,
                "message": "Email changed successfully",
                "new_email": updated_email,
            },
        )
    except InvalidCurrentPasswordError:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Password is incorrect",
            },
        )
    except EmailExistsError:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "This email is already in use",
            },
        )
