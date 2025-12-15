"""Authentication endpoints."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.database import get_db
from app.core.models import User
from app.schemas.auth import (
    EmailChange,
    EmailChangeResult,
    PasswordChange,
    PasswordChangeResult,
    Token,
    UserCreate,
    UserResponse,
)
from app.services import (
    AuthService,
    EmailExistsError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    RegistrationDisabledError,
    UsernameExistsError,
)

ROUTER = APIRouter(prefix="/auth", tags=["Authentication"])


@ROUTER.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register a new user.

    Args:
        user_data (UserCreate): The user registration data.
        db (AsyncSession): The database session.

    Returns:
        UserResponse: The registered user data.
    """
    try:
        return (
            await AuthService(db).register_user(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,
            )
        ).user
    except RegistrationDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except EmailExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UsernameExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: t.Annotated[OAuth2PasswordRequestForm, Depends()],
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """Authenticate user and return access token.

    Args:
        form_data (OAuth2PasswordRequestForm): The login form data.
        db (AsyncSession): The database session.

    Returns:
        Token: The access token.
    """
    try:
        return (
            await AuthService(db).login(form_data.username, form_data.password)
        ).token
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@ROUTER.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get current user information.

    Args:
        current_user (User): The currently authenticated user.

    Returns:
        UserResponse: The current user data.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@ROUTER.post("/change-password", response_model=PasswordChangeResult)
async def change_password(
    password_data: PasswordChange,
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> PasswordChangeResult:
    """Change the current user's password.

    Args:
        password_data (PasswordChange): The password change request data.
        current_user (User): The currently authenticated user.
        db (AsyncSession): The database session.

    Returns:
        PasswordChangeResult: The result of the password change operation.
    """
    try:
        await AuthService(db).change_password(
            user=current_user,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )
        return PasswordChangeResult(
            success=True,
            message="Password changed successfully",
        )
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.post("/change-email", response_model=EmailChangeResult)
async def change_email(
    email_data: EmailChange,
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> EmailChangeResult:
    """Change the current user's email address.

    Args:
        email_data (EmailChange): The email change request data.
        current_user (User): The currently authenticated user.
        db (AsyncSession): The database session.

    Returns:
        EmailChangeResult: The result of the email change operation.
    """
    try:
        new_email: str = await AuthService(db).change_email(
            user=current_user,
            new_email=email_data.new_email,
            password=email_data.password,
        )
        return EmailChangeResult(
            success=True,
            message="Email changed successfully",
            new_email=new_email,
        )
    except InvalidCurrentPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except EmailExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
