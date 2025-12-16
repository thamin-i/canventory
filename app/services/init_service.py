"""Initialization service for seeding database with default data."""

import logging
import secrets
import string
import typing as t

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.core.models import Category, User

LOGGER: logging.Logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES: t.List[t.Dict[str, str]] = [
    {"value": "canned_vegetables", "label": "Canned Vegetables", "icon": "🥕"},
    {"value": "canned_fruits", "label": "Canned Fruits", "icon": "🍑"},
    {"value": "canned_meats", "label": "Canned Meats", "icon": "🥩"},
    {"value": "canned_soups", "label": "Canned Soups", "icon": "🍲"},
    {"value": "grains", "label": "Grains", "icon": "🌾"},
    {"value": "pasta", "label": "Pasta", "icon": "🍝"},
    {"value": "rice", "label": "Rice", "icon": "🍚"},
    {"value": "cereals", "label": "Cereals", "icon": "🥣"},
    {"value": "beans", "label": "Beans", "icon": "🫘"},
    {"value": "nuts", "label": "Nuts", "icon": "🥜"},
    {"value": "dried_fruits", "label": "Dried Fruits", "icon": "🍇"},
    {"value": "condiments", "label": "Condiments", "icon": "🧂"},
    {"value": "oils", "label": "Oils", "icon": "🫒"},
    {"value": "baking", "label": "Baking", "icon": "🧁"},
    {"value": "snacks", "label": "Snacks", "icon": "🍿"},
    {"value": "beverages", "label": "Beverages", "icon": "🧃"},
    {"value": "baby_food", "label": "Baby Food", "icon": "🍼"},
    {"value": "pet_food", "label": "Pet Food", "icon": "🐕"},
    {"value": "other", "label": "Other", "icon": "📦"},
]


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


async def seed_categories(db: AsyncSession) -> int:
    """Seed the database with default categories if none exist.

    Args:
        db (AsyncSession): The database session.

    Returns:
        int: Number of categories created.
    """
    existing: Category | None = (
        (await db.execute(select(Category))).scalars().first()
    )
    if existing is not None:
        LOGGER.debug("Categories already exist, skipping seed")
        return 0

    LOGGER.info(
        "Seeding database with %d default categories", len(DEFAULT_CATEGORIES)
    )
    for idx, cat_data in enumerate(DEFAULT_CATEGORIES):
        category: Category = Category(
            value=cat_data["value"],
            label=cat_data["label"],
            icon=cat_data["icon"],
            sort_order=idx,
        )
        db.add(category)

    await db.flush()
    LOGGER.info("Successfully seeded %d categories", len(DEFAULT_CATEGORIES))
    return len(DEFAULT_CATEGORIES)


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


async def migrate_category_column(db: AsyncSession) -> bool:
    """Migrate the category column from enum to varchar if needed.

    This is a one-time migration for databases created before dynamic
    categories were implemented. It converts the old PostgreSQL enum
    type to a VARCHAR column.

    Args:
        db (AsyncSession): The database session.

    Returns:
        bool: True if migration was performed, False otherwise.
    """
    try:
        # Check if the foodcategory enum type exists
        result = await db.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_type WHERE typname = 'foodcategory'"
                ")"
            )
        )
        enum_exists = result.scalar()

        if not enum_exists:
            LOGGER.debug("No foodcategory enum found, skipping migration")
            return False

        # Check if food_items table exists
        result = await db.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'food_items'"
                ")"
            )
        )
        table_exists = result.scalar()

        if not table_exists:
            LOGGER.debug("food_items table not found, skipping migration")
            return False

        # Check if category column is still using the enum type
        result = await db.execute(
            text(
                "SELECT data_type, udt_name FROM information_schema.columns "
                "WHERE table_name = 'food_items' AND column_name = 'category'"
            )
        )
        row = result.fetchone()

        if row is None:
            LOGGER.debug("category column not found, skipping migration")
            return False

        if row[1] != "foodcategory":
            LOGGER.debug("category column already migrated to %s", row[1])
            return False

        LOGGER.info("Migrating category column from enum to varchar...")

        # Alter the column type from enum to varchar
        await db.execute(
            text(
                "ALTER TABLE food_items "
                "ALTER COLUMN category TYPE VARCHAR(50) "
                "USING category::text"
            )
        )

        # Drop the old enum type
        await db.execute(text("DROP TYPE IF EXISTS foodcategory"))

        await db.commit()
        LOGGER.info("Category column migration completed successfully")
        return True

    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.warning("Category migration check failed: %s", exc)
        await db.rollback()
        return False


async def initialize_database(db: AsyncSession) -> None:
    """Initialize the database with default data.

    This function should be called at application startup to ensure
    the database has all required seed data.

    Args:
        db (AsyncSession): The database session.
    """
    LOGGER.info("Running database initialization...")

    migrated: bool = await migrate_category_column(db)
    if migrated:
        LOGGER.info("Database migration completed")

    categories_created: int = await seed_categories(db)
    if categories_created > 0:
        LOGGER.info("Created %d categories", categories_created)

    admin_created: bool = await create_admin_user(db)
    if admin_created:
        LOGGER.info("Admin user created successfully")

    await db.commit()
    LOGGER.info("Database initialization complete")
