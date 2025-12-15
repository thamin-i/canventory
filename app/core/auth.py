"""Authentication utilities and dependencies."""

import typing as t
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher, Type
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPBasic,
    HTTPBasicCredentials,
    OAuth2PasswordBearer,
)
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SETTINGS
from app.core.database import get_db
from app.core.models import SystemSettings, User
from app.schemas.auth import TokenData

OAUTH2_SCHEME: OAuth2PasswordBearer = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token", auto_error=False
)
HTTP_BASIC: HTTPBasic = HTTPBasic(auto_error=False)

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its Argon2id hash.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The hashed password to compare against.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    try:
        PASSWORD_HASHER.verify(hashed_password, plain_password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be rehashed.

    Args:
        hashed_password (str): The hashed password to check.

    Returns:
        bool:
            True if the Argon2 parameters have been updated since
            the password was last hashed.
    """
    try:
        return PASSWORD_HASHER.check_needs_rehash(hashed_password)
    except (InvalidHashError, ValueError):
        return True


def get_password_hash(password: str) -> str:
    """Hash a password for storing using Argon2id.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The Argon2id hashed password with embedded salt and parameters.
    """
    return PASSWORD_HASHER.hash(password)


def create_access_token(
    data: t.Dict[str, t.Any], expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token.

    Args:
        data (t.Dict[str, t.Any]):
            The data to encode in the token.
        expires_delta (timedelta | None):
            Optional expiration time for the token.

    Returns:
        str: The encoded JWT token.
    """
    to_encode: t.Dict[str, t.Any] = data.copy()
    expire: datetime
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=SETTINGS.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    return str(
        jwt.encode(to_encode, SETTINGS.secret_key, algorithm=SETTINGS.algorithm)
    )


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Get a user by username.

    Args:
        db (AsyncSession): The database session.
        username (str): The username to search for.

    Returns:
        User | None: The user object if found, else None.
    """
    return (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get a user by email.

    Args:
        db (AsyncSession): The database session.
        email (str): The email to search for.

    Returns:
        User | None: The user object if found, else None.
    """
    return (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get a user by ID.

    Args:
        db (AsyncSession): The database session.
        user_id (int): The user ID to search for.

    Returns:
        User | None: The user object if found, else None.
    """
    return (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    """Authenticate a user with username and password.

    Args:
        db (AsyncSession):
            The database session.
        username (str):
            The username of the user.
        password (str):
            The plain text password of the user.

    Returns:
        User | None:
            The authenticated user object if credentials are valid,
            else None.
    """
    user: User | None = await get_user_by_username(db, username)

    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(password)
        await db.flush()

    return user


async def get_current_user_from_token(
    token: str, db: AsyncSession
) -> User | None:
    """Extract user from JWT token.

    Args:
        token (str): The JWT token.
        db (AsyncSession): The database session.

    Returns:
        User | None: The user object if token is valid, else None.
    """
    try:
        payload: t.Dict[str, t.Any] = jwt.decode(
            token, SETTINGS.secret_key, algorithms=[SETTINGS.algorithm]
        )
        username: str = payload.get("sub", "[UNKNOWN]")
        user_id: int = payload.get("user_id", "[UNKNOWN]")
        if username is None:
            return None
        token_data: TokenData = TokenData(username=username, user_id=user_id)
    except JWTError:
        return None

    return await get_user_by_username(db, token_data.username or "[UNKNOWN]")


async def get_current_user(
    token: t.Annotated[str | None, Depends(OAUTH2_SCHEME)],
    basic_credentials: t.Annotated[
        HTTPBasicCredentials | None, Depends(HTTP_BASIC)
    ],
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user (supports both JWT and Basic Auth).

    Args:
        token (str | None):
            The JWT token from the Authorization header.
        basic_credentials (HTTPBasicCredentials | None):
            The Basic Auth credentials.
        db (AsyncSession):
            The database session.

    Returns:
        User: The authenticated user.
    """
    user: User | None = None
    if token is not None:
        user = await get_current_user_from_token(token, db)
    elif user is None and basic_credentials is not None:
        user = await authenticate_user(
            db, basic_credentials.username, basic_credentials.password
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: t.Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure the current user is active.

    Args:
        current_user (User): The current authenticated user.

    Returns:
        User: The active user.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def is_registration_enabled(db: AsyncSession) -> bool:
    """Check if new user registration is enabled.

    Args:
        db (AsyncSession): The database session.

    Returns:
        bool: True if registration is enabled, False otherwise.
    """
    setting: SystemSettings | None = (
        await db.execute(
            select(SystemSettings).where(
                SystemSettings.key == "registration_enabled"
            )
        )
    ).scalar_one_or_none()

    if setting is None:
        return await set_registration_enabled(db, False)

    return setting.value.lower() == "true"


async def set_registration_enabled(db: AsyncSession, enabled: bool) -> bool:
    """Set whether new user registration is enabled.

    Args:
        db (AsyncSession): The database session.
        enabled (bool): Whether registration should be enabled.

    Returns:
        bool: The new registration enabled status.
    """
    setting: SystemSettings | None = (
        await db.execute(
            select(SystemSettings).where(
                SystemSettings.key == "registration_enabled"
            )
        )
    ).scalar_one_or_none()

    if setting is None:
        db.add(
            SystemSettings(
                key="registration_enabled",
                value=str(enabled).lower(),
            )
        )
    else:
        setting.value = str(enabled).lower()

    await db.flush()
    return enabled


async def get_current_web_user(
    request: Request, db: AsyncSession
) -> User | None:
    """Get current user from session cookie.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        User | None:
            The current user or None if not authenticated.
    """
    user_id: str | None = request.cookies.get("user_id")
    if user_id is None:
        return None
    try:
        return await get_user_by_id(db, int(user_id))
    except (ValueError, TypeError):
        return None
