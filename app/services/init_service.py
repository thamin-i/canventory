"""Initialization service for seeding database with default data."""

import logging
import secrets
import string
import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.core.models import User

LOGGER: logging.Logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.

    Args:
        length (int): Length of the password. Defaults to 16.

    Returns:
        str: A secure random password.
    """
    alphabet: str = string.ascii_letters + string.digits + string.punctuation
    password: t.List[str] = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))
    password_list: t.List[str] = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return "".join(password_list)


async def create_admin_user(db: AsyncSession) -> bool:
    """Create the default admin user if no admin exists.

    Args:
        db (AsyncSession): The database session.

    Returns:
        bool: True if admin was created, False if already exists.
    """
    existing_admin: User | None = (
        await db.execute(select(User).where(User.username == "admin"))
    ).scalar_one_or_none()

    if existing_admin is not None:
        LOGGER.debug("Admin user already exists, skipping creation")
        return False

    password: str = generate_secure_password(16)
    hashed_password: str = get_password_hash(password)

    admin_user: User = User(
        username="admin",
        email="admin@admin.admin",
        hashed_password=hashed_password,
        is_admin=True,
        is_active=True,
    )
    db.add(admin_user)
    await db.flush()

    LOGGER.warning("=" * 60)
    LOGGER.warning("ADMIN USER CREATED")
    LOGGER.warning("=" * 60)
    LOGGER.warning("Username: admin")
    LOGGER.warning("Email: admin@admin.admin")
    LOGGER.warning("Password: %s", password)
    LOGGER.warning("=" * 60)
    LOGGER.warning("PLEASE CHANGE THIS PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")
    LOGGER.warning("=" * 60)

    return True


async def initialize_database(db: AsyncSession) -> None:
    """Initialize the database with default data.

    This function should be called at application startup to ensure
    the database has all required seed data.

    Note: Categories are now created per-home when a home is created,
    so we no longer seed global categories.

    Args:
        db (AsyncSession): The database session.
    """
    LOGGER.info("Running database initialization...")

    admin_created: bool = await create_admin_user(db)
    if admin_created:
        LOGGER.info("Admin user created successfully")

    await db.commit()
    LOGGER.info("Database initialization complete")
