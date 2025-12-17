"""Category utilities (home-scoped)."""

import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Category


async def get_categories(
    db: AsyncSession,
    home_id: int,
) -> t.List[t.Dict[str, str]]:
    """Fetch all categories from the database for a specific home.

    Args:
        db (AsyncSession): The database session.
        home_id (int): The ID of the home.

    Returns:
        List[Dict[str, str]]:
            List of category dictionaries with 'value' and 'label' keys.
    """
    categories = (
        (
            await db.execute(
                select(Category)
                .where(Category.home_id == home_id)
                .order_by(Category.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return [
        {"value": cat.value, "label": f"{cat.icon} {cat.label}"}
        for cat in categories
    ]


async def get_category_icons(
    db: AsyncSession,
    home_id: int,
) -> t.Dict[str, str]:
    """Fetch category icons mapping from the database for a specific home.

    Args:
        db (AsyncSession): The database session.
        home_id (int): The ID of the home.

    Returns:
        Dict[str, str]: Mapping of category value to icon.
    """
    categories = (
        (await db.execute(select(Category).where(Category.home_id == home_id)))
        .scalars()
        .all()
    )
    return {cat.value: cat.icon for cat in categories}
