"""Category service for CRUD operations."""

import logging
import typing as t

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Category, FoodItem

LOGGER: logging.Logger = logging.getLogger(__name__)


class CategoryNotFoundError(Exception):
    """Exception raised when a category is not found."""

    category_id: int

    def __init__(self, category_id: int) -> None:
        """Initialize the exception.

        Args:
            category_id: The ID of the category that was not found.
        """
        self.category_id = category_id
        super().__init__(f"Category with ID {category_id} not found")


class CategoryInUseError(Exception):
    """Exception raised when a category is in use and cannot be deleted."""

    category_id: int
    item_count: int

    def __init__(self, category_id: int, item_count: int) -> None:
        """Initialize the exception.

        Args:
            category_id: The ID of the category.
            item_count: Number of items using this category.
        """
        self.category_id = category_id
        self.item_count = item_count
        super().__init__(
            f"Category is used by {item_count} item(s) and cannot be deleted"
        )


class CategoryValueExistsError(Exception):
    """Exception raised when a category value already exists."""

    value: str

    def __init__(self, value: str) -> None:
        """Initialize the exception.

        Args:
            value: The category value that already exists.
        """
        self.value = value
        super().__init__(f"Category with value '{value}' already exists")


class CategoryService:
    """Service class for category operations."""

    db: AsyncSession

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service.

        Args:
            db: The async database session.
        """
        self.db = db

    async def list_categories(self) -> t.List[Category]:
        """List all categories ordered by sort_order.

        Returns:
            List of all categories.
        """
        result: t.Sequence[Category] = (
            (
                await self.db.execute(
                    select(Category).order_by(Category.sort_order, Category.id)
                )
            )
            .scalars()
            .all()
        )
        return list(result)

    async def get_category(self, category_id: int) -> Category:
        """Get a category by ID.

        Args:
            category_id: The ID of the category.

        Returns:
            The category.

        Raises:
            CategoryNotFoundError: If the category is not found.
        """
        category: Category | None = (
            await self.db.execute(
                select(Category).where(Category.id == category_id)
            )
        ).scalar_one_or_none()
        if category is None:
            raise CategoryNotFoundError(category_id)
        return category

    async def get_category_by_value(self, value: str) -> Category | None:
        """Get a category by value.

        Args:
            value: The value of the category.

        Returns:
            The category or None if not found.
        """
        return (
            await self.db.execute(
                select(Category).where(Category.value == value)
            )
        ).scalar_one_or_none()

    async def create_category(
        self,
        value: str,
        label: str,
        icon: str,
        sort_order: int = 0,
    ) -> Category:
        """Create a new category.

        Args:
            value: The unique value identifier for the category.
            label: The display label for the category.
            icon: The emoji icon for the category.
            sort_order: The sort order for the category.

        Returns:
            The created category.

        Raises:
            CategoryValueExistsError: If a category with the value exists.
        """
        existing: Category | None = await self.get_category_by_value(value)
        if existing is not None:
            raise CategoryValueExistsError(value)

        category: Category = Category(
            value=value,
            label=label,
            icon=icon,
            sort_order=sort_order,
        )
        self.db.add(category)
        try:
            await self.db.flush()
            await self.db.refresh(category)
        except IntegrityError as exc:
            await self.db.rollback()
            raise CategoryValueExistsError(value) from exc

        LOGGER.info("Created category: %s (%s)", label, value)
        return category

    async def update_category(
        self,
        category_id: int,
        label: str | None = None,
        icon: str | None = None,
        sort_order: int | None = None,
    ) -> Category:
        """Update an existing category.

        Args:
            category_id: The ID of the category to update.
            label: The new display label (optional).
            icon: The new emoji icon (optional).
            sort_order: The new sort order (optional).

        Returns:
            The updated category.

        Raises:
            CategoryNotFoundError: If the category is not found.
        """
        category: Category = await self.get_category(category_id)

        if label is not None:
            category.label = label
        if icon is not None:
            category.icon = icon
        if sort_order is not None:
            category.sort_order = sort_order

        await self.db.flush()
        await self.db.refresh(category)

        LOGGER.info(
            "Updated category: %s (ID: %d)", category.label, category_id
        )
        return category

    async def delete_category(
        self, category_id: int, force: bool = False
    ) -> None:
        """Delete a category.

        Args:
            category_id: The ID of the category to delete.
            force: If True, reassign items to 'other' category before deletion.

        Raises:
            CategoryNotFoundError: If the category is not found.
            CategoryInUseError: If the category is in use and force is False.
        """
        category: Category = await self.get_category(category_id)

        # Check if category is in use
        item_count: int = (
            await self.db.execute(
                select(
                    func.count(FoodItem.id)  # pylint: disable=not-callable
                ).where(FoodItem.category == category.value)
            )
        ).scalar() or 0

        if item_count > 0 and not force:
            raise CategoryInUseError(category_id, item_count)

        # If force delete, reassign items to 'other' category
        if item_count > 0 and force:
            other_category: Category | None = await self.get_category_by_value(
                "other"
            )
            if other_category is None:
                # Create 'other' category if it doesn't exist
                other_category = await self.create_category(
                    value="other",
                    label="Other",
                    icon="📦",
                    sort_order=999,
                )

            # Update all items with this category to 'other'
            items_result: t.Sequence[FoodItem] = (
                (
                    await self.db.execute(
                        select(FoodItem).where(
                            FoodItem.category == category.value
                        )
                    )
                )
                .scalars()
                .all()
            )
            for item in items_result:
                item.category = other_category.value

            await self.db.flush()
            LOGGER.info(
                "Reassigned %d items from category %s to 'other'",
                item_count,
                category.value,
            )

        await self.db.delete(category)
        await self.db.flush()

        LOGGER.info(
            "Deleted category: %s (ID: %d)", category.label, category_id
        )

    async def get_category_item_count(self, category_id: int) -> int:
        """Get the number of items using a category.

        Args:
            category_id: The ID of the category.

        Returns:
            The number of items using this category.

        Raises:
            CategoryNotFoundError: If the category is not found.
        """
        category: Category = await self.get_category(category_id)
        result: int = (
            await self.db.execute(
                select(
                    func.count(FoodItem.id)  # pylint: disable=not-callable
                ).where(FoodItem.category == category.value)
            )
        ).scalar() or 0
        return result
