"""Storage location utilities (home-scoped)."""

import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import StorageLocation


async def get_locations(
    db: AsyncSession,
    home_id: int,
) -> t.List[t.Dict[str, t.Any]]:
    """Fetch all storage locations from the database for a specific home.

    Args:
        db (AsyncSession): The database session.
        home_id (int): The ID of the home.

    Returns:
        List[Dict[str, Any]]:
            List of location dictionaries with 'id' and 'name' keys.
    """
    locations = (
        (
            await db.execute(
                select(StorageLocation)
                .where(StorageLocation.home_id == home_id)
                .order_by(StorageLocation.name)
            )
        )
        .scalars()
        .all()
    )
    return [{"id": loc.id, "name": loc.name} for loc in locations]
