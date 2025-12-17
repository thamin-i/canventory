"""Storage location service for CRUD operations (home-scoped)."""

import logging
import typing as t

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import FoodItem, StorageLocation

LOGGER: logging.Logger = logging.getLogger(__name__)


class LocationNotFoundError(Exception):
    """Exception raised when a storage location is not found."""

    location_id: int

    def __init__(self, location_id: int) -> None:
        """Initialize the exception.

        Args:
            location_id: The ID of the location that was not found.
        """
        self.location_id = location_id
        super().__init__(f"Storage location with ID {location_id} not found")


class LocationInUseError(Exception):
    """Exception raised when a location is in use and cannot be deleted."""

    location_id: int
    item_count: int

    def __init__(self, location_id: int, item_count: int) -> None:
        """Initialize the exception.

        Args:
            location_id: The ID of the location.
            item_count: Number of items using this location.
        """
        self.location_id = location_id
        self.item_count = item_count
        super().__init__(
            f"Location is used by {item_count} item(s) and cannot be deleted"
        )


class LocationNameExistsError(Exception):
    """Exception raised when a location name already exists."""

    name: str

    def __init__(self, name: str) -> None:
        """Initialize the exception.

        Args:
            name: The location name that already exists.
        """
        self.name = name
        super().__init__(f"Location with name '{name}' already exists")


class LocationService:
    """Service class for storage location operations (home-scoped)."""

    db: AsyncSession
    home_id: int

    def __init__(self, db: AsyncSession, home_id: int) -> None:
        """Initialize the service.

        Args:
            db: The async database session.
            home_id: The ID of the home to scope operations to.
        """
        self.db = db
        self.home_id = home_id

    async def list_locations(self) -> t.List[StorageLocation]:
        """List all storage locations for the home ordered by name.

        Returns:
            List of all storage locations in the home.
        """
        result: t.Sequence[StorageLocation] = (
            (
                await self.db.execute(
                    select(StorageLocation)
                    .where(StorageLocation.home_id == self.home_id)
                    .order_by(StorageLocation.name)
                )
            )
            .scalars()
            .all()
        )
        return list(result)

    async def get_location(self, location_id: int) -> StorageLocation:
        """Get a storage location by ID (must belong to the home).

        Args:
            location_id: The ID of the location.

        Returns:
            The storage location.
        """
        location: StorageLocation | None = (
            await self.db.execute(
                select(StorageLocation).where(
                    StorageLocation.id == location_id,
                    StorageLocation.home_id == self.home_id,
                )
            )
        ).scalar_one_or_none()
        if location is None:
            raise LocationNotFoundError(location_id)
        return location

    async def get_location_by_name(self, name: str) -> StorageLocation | None:
        """Get a storage location by name within the home.

        Args:
            name: The name of the location.

        Returns:
            The storage location or None if not found.
        """
        return (
            await self.db.execute(
                select(StorageLocation).where(
                    StorageLocation.name == name,
                    StorageLocation.home_id == self.home_id,
                )
            )
        ).scalar_one_or_none()

    async def get_or_create_location(self, name: str) -> StorageLocation:
        """Get a storage location by name or create it if it doesn't exist.

        Args:
            name: The name of the location.

        Returns:
            The existing or newly created storage location.
        """
        # Normalize the name (trim whitespace)
        name = name.strip()
        if not name:
            raise ValueError("Location name cannot be empty")

        existing: StorageLocation | None = await self.get_location_by_name(name)
        if existing is not None:
            return existing

        return await self.create_location(name)

    async def create_location(self, name: str) -> StorageLocation:
        """Create a new storage location in the home.

        Args:
            name: The name for the location.

        Returns:
            The created storage location.
        """
        # Normalize the name
        name = name.strip()
        if not name:
            raise ValueError("Location name cannot be empty")

        existing: StorageLocation | None = await self.get_location_by_name(name)
        if existing is not None:
            raise LocationNameExistsError(name)

        location: StorageLocation = StorageLocation(
            home_id=self.home_id,
            name=name,
        )
        self.db.add(location)
        try:
            await self.db.flush()
            await self.db.refresh(location)
        except IntegrityError as exc:
            await self.db.rollback()
            raise LocationNameExistsError(name) from exc

        LOGGER.info(
            "Created storage location: %s in home %d", name, self.home_id
        )
        return location

    async def update_location(
        self,
        location_id: int,
        name: str | None = None,
    ) -> StorageLocation:
        """Update an existing storage location.

        Args:
            location_id: The ID of the location to update.
            name: The new name (optional).

        Returns:
            The updated storage location.
        """
        location: StorageLocation = await self.get_location(location_id)

        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Location name cannot be empty")

            # Check if new name already exists
            existing = await self.get_location_by_name(name)
            if existing is not None and existing.id != location_id:
                raise LocationNameExistsError(name)

            location.name = name

        await self.db.flush()
        await self.db.refresh(location)

        LOGGER.info(
            "Updated storage location: %s (ID: %d)", location.name, location_id
        )
        return location

    async def delete_location(
        self, location_id: int, force: bool = False
    ) -> None:
        """Delete a storage location.

        Args:
            location_id: The ID of the location to delete.
            force: If True, unset location for all items using it.
        """
        location: StorageLocation = await self.get_location(location_id)

        # Check if location is in use
        item_count: int = (
            await self.db.execute(
                select(
                    func.count(FoodItem.id)  # pylint: disable=not-callable
                ).where(
                    FoodItem.location_id == location_id,
                    FoodItem.home_id == self.home_id,
                )
            )
        ).scalar() or 0

        if item_count > 0 and not force:
            raise LocationInUseError(location_id, item_count)

        # If force delete, unset location for all items
        if item_count > 0 and force:
            items_result: t.Sequence[FoodItem] = (
                (
                    await self.db.execute(
                        select(FoodItem).where(
                            FoodItem.location_id == location_id,
                            FoodItem.home_id == self.home_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for item in items_result:
                item.location_id = None

            await self.db.flush()
            LOGGER.info(
                "Cleared location from %d items before deleting location %s",
                item_count,
                location.name,
            )

        await self.db.delete(location)
        await self.db.flush()

        LOGGER.info(
            "Deleted storage location: %s (ID: %d)", location.name, location_id
        )

    async def get_location_item_count(self, location_id: int) -> int:
        """Get the number of items using a storage location.

        Args:
            location_id: The ID of the location.

        Returns:
            The number of items using this location.
        """
        await self.get_location(location_id)  # Verify location exists
        result: int = (
            await self.db.execute(
                select(
                    func.count(FoodItem.id)  # pylint: disable=not-callable
                ).where(
                    FoodItem.location_id == location_id,
                    FoodItem.home_id == self.home_id,
                )
            )
        ).scalar() or 0
        return result
