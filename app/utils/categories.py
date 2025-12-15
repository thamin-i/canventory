"""Category utilities."""

import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Category


async def get_categories(
    db: AsyncSession,
) -> t.List[t.Dict[str, str]]:
    """Fetch all categories from the database.

    Args:
        db (AsyncSession): The database session.

    Returns:
        List[Dict[str, str]]:
            List of category dictionaries with 'value' and 'label' keys.
    """
    result = await db.execute(select(Category).order_by(Category.sort_order))
    categories = result.scalars().all()
    return [
        {"value": cat.value, "label": f"{cat.icon} {cat.label}"}
        for cat in categories
    ]


async def get_category_icons(
    db: AsyncSession,
) -> t.Dict[str, str]:
    """Fetch category icons mapping from the database.

    Args:
        db (AsyncSession): The database session.

    Returns:
        Dict[str, str]: Mapping of category value to icon.
    """
    result = await db.execute(select(Category))
    categories = result.scalars().all()
    return {cat.value: cat.icon for cat in categories}
