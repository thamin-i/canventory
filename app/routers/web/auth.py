"""Web authentication routes."""

import typing as t

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import User
from app.schemas.auth import RegistrationResult
from app.services import (
    AuthService,
    EmailExistsError,
    RegistrationDisabledError,
    UsernameExistsError,
)

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    error: str | None = None,
    success: str | None = None,
) -> HTMLResponse:
    """Render login page.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        error (str | None): An optional error message to display.
        success (str | None): An optional success message to display.

    Returns:
        HTMLResponse: The rendered login page.
    """
    return t.cast(
        HTMLResponse,
        TEMPLATES.TemplateResponse(
            "pages/login.html",
            {
                "request": request,
                "error": error,
                "success": success,
                "registration_enabled": await AuthService(
                    db
                ).check_registration_enabled(),
            },
        ),
    )


@ROUTER.post("/login", response_model=None)
async def login_submit(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    """Handle login form submission.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        username (str): The submitted username.
        password (str): The submitted password.

    Returns:
        RedirectResponse | HTMLResponse:
            A redirect to the dashboard on success,
            or the login page with an error on failure.
    """
    user: User | None = await AuthService(db).authenticate(username, password)
    if user is None:
        return t.cast(
            HTMLResponse,
            TEMPLATES.TemplateResponse(
                "pages/login.html",
                {"request": request, "error": "Invalid username or password"},
            ),
        )

    response: RedirectResponse = RedirectResponse(
        url="/web/dashboard", status_code=303
    )
    response.set_cookie(
        key="user_id",
        value=str(user.id),
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax",
    )
    return response


@ROUTER.post("/register", response_model=None)
async def register_submit(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    """Handle registration form submission.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        username (str): The desired username.
        email (str): The desired email.
        password (str): The desired password.

    Returns:
        RedirectResponse | HTMLResponse:
            A redirect to the login page on success,
            or the login page with an error on failure.
    """
    service: AuthService = AuthService(db)
    try:
        result: RegistrationResult = await service.register_user(
            username=username,
            email=email,
            password=password,
        )

        success_msg: str = (
            "Account created! You are the admin."
            if result.is_first_user
            else "Account created! Please log in."
        )
        return RedirectResponse(
            url=f"/web/login?success={success_msg}", status_code=303
        )

    except RegistrationDisabledError:
        return t.cast(
            HTMLResponse,
            TEMPLATES.TemplateResponse(
                "pages/login.html",
                {
                    "request": request,
                    "error": "New registrations are currently disabled",
                    "registration_enabled": False,
                },
            ),
        )
    except UsernameExistsError:
        return t.cast(
            HTMLResponse,
            TEMPLATES.TemplateResponse(
                "pages/login.html",
                {
                    "request": request,
                    "error": "Username already registered",
                    "registration_enabled": await service.check_registration_enabled(),  # pylint: disable=line-too-long  # noqa: E501
                },
            ),
        )
    except EmailExistsError:
        return t.cast(
            HTMLResponse,
            TEMPLATES.TemplateResponse(
                "pages/login.html",
                {
                    "request": request,
                    "error": "Email already registered",
                    "registration_enabled": await service.check_registration_enabled(),  # pylint: disable=line-too-long  # noqa: E501
                },
            ),
        )


@ROUTER.get("/logout")
async def logout() -> RedirectResponse:
    """Handle logout.

    Returns:
        RedirectResponse: A redirect to the login page.
    """
    response: RedirectResponse = RedirectResponse(
        url="/web/login", status_code=303
    )
    response.delete_cookie(key="user_id")
    return response


@ROUTER.get("/")
async def web_root() -> RedirectResponse:
    """Redirect root to login.

    Returns:
        RedirectResponse: A redirect to the login page.
    """
    return RedirectResponse(url="/web/login", status_code=303)
