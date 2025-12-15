"""Item service - business logic for food item operations."""

import base64
import binascii
import os
import typing as t
import uuid
from datetime import datetime
from datetime import timedelta as td
from datetime import timezone
from pathlib import Path

from sqlalchemy import Select, UnaryExpression, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SETTINGS
from app.core.models import ExpirationStatus, FoodCategory, FoodItem
from app.schemas.alert import ExpirationAlert, ExpirationAlertSummary
from app.schemas.food_item import FoodItemListResponse, FoodItemResponse
from app.schemas.statistics import FoodClosetStats
from app.utils.dates import calculate_days_until_expiration


class ItemNotFoundError(Exception):
    """Raised when an item is not found."""

    def __init__(self, item_id: int) -> None:
        self.item_id = item_id
        super().__init__(f"Food item with ID {item_id} not found")


class InvalidImageError(Exception):
    """Raised when image data is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ImageTooLargeError(Exception):
    """Raised when image exceeds size limit."""

    max_size_mb: float

    def __init__(self, max_size_mb: float) -> None:
        """Initialize ImageTooLargeError.

        Args:
            max_size_mb (float): The maximum allowed image size in megabytes.
        """
        self.max_size_mb = max_size_mb
        super().__init__(f"Image size exceeds maximum of {max_size_mb}MB")


class ItemService:
    """Service class for food item operations."""

    db: AsyncSession

    def __init__(self, db: AsyncSession) -> None:
        """Initialize ItemService.

        Args:
            db (AsyncSession): The database session.
        """
        self.db = db

    def convert_item_to_response(self, item: FoodItem) -> FoodItemResponse:
        """Convert FoodItem model to FoodItemResponse schema.

        Args:
            item (FoodItem): The food item model.

        Returns:
            FoodItemResponse: The food item response schema.
        """
        days: int = calculate_days_until_expiration(item.expiration_date)
        has_image: bool = bool(item.image_path or item.image_data)

        return FoodItemResponse(
            id=item.id,
            name=item.name,
            quantity=item.quantity,
            expiration_date=item.expiration_date,
            category=item.category,
            description=item.description,
            expiration_status=item.get_expiration_status(
                SETTINGS.expiration_warning_days,
                SETTINGS.expiration_critical_days,
            ),
            days_until_expiration=days,
            has_image=has_image,
            image_url=f"/api/items/{item.id}/image" if has_image else None,
            created_at=item.created_at,
            updated_at=item.updated_at or item.created_at,
            created_by=item.created_by,
        )

    async def save_image_from_b64(
        self, image_base64: str, item_id: int
    ) -> tuple[str | None, bytes | None, str | None]:
        """Save image from base64 string.

        Args:
            image_base64 (str): The base64-encoded image string.
            item_id (int): The ID of the food item.

        Returns:
            tuple[str | None, bytes | None, str | None]:
                A tuple containing the image path (if stored on filesystem),
                image data (if stored in database), and MIME type.
        """
        try:
            # Decode base64
            if "," in image_base64:
                # Handle data URL format (e.g., data:image/png;base64,...)
                header, image_base64 = image_base64.split(",", 1)
                mime_type: str = (
                    header.split(":")[1].split(";")[0]
                    if ":" in header
                    else "image/jpeg"
                )
            else:
                mime_type = "image/jpeg"

            image_data: bytes = base64.b64decode(image_base64)
            return self._process_image_data(image_data, item_id, mime_type)

        except binascii.Error as exc:
            raise InvalidImageError("Invalid base64 image data") from exc

    def _process_image_data(
        self, image_data: bytes, item_id: int, mime_type: str | None = None
    ) -> tuple[str | None, bytes | None, str | None]:
        """Process and save raw image data.

        Args:
            image_data (bytes): The raw image data.
            item_id (int): The ID of the food item.
            mime_type (str | None): The MIME type of the image.

        Returns:
            tuple[str | None, bytes | None, str | None]:
                A tuple containing the image path (if stored on filesystem),
                image data (if stored in database), and MIME type.
        """
        # Validate image size
        max_size: int = SETTINGS.max_image_size_mb * 1024 * 1024
        if len(image_data) > max_size:
            raise ImageTooLargeError(SETTINGS.max_image_size_mb)

        effective_mime: str = mime_type or "image/jpeg"

        if SETTINGS.image_storage == "filesystem":
            # Save to filesystem
            extension: str = effective_mime.split("/")[-1]
            filename: str = f"{item_id}_{uuid.uuid4().hex}.{extension}"
            filepath: Path = SETTINGS.image_upload_dir / filename

            with open(filepath, "wb") as f:
                f.write(image_data)

            return str(filepath), None, effective_mime

        # Store in database
        return None, image_data, effective_mime

    @staticmethod
    def delete_image_file(image_path: str | None) -> None:
        """Delete image file from filesystem.

        Args:
            image_path (str | None): The path to the image file.
        """
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

    async def get_item(self, item_id: int) -> FoodItemResponse:
        """Get a specific food item by ID.

        Args:
            item_id (int): The ID of the food item.

        Returns:
            FoodItemResponse: The food item response schema.
        """
        item: FoodItem | None = (
            await self.db.execute(
                select(FoodItem).where(FoodItem.id == item_id)
            )
        ).scalar_one_or_none()

        if item is None:
            raise ItemNotFoundError(item_id)

        return self.convert_item_to_response(item)

    async def get_item_model(self, item_id: int) -> FoodItem:
        """Get the raw FoodItem model by ID.

        Args:
            item_id (int): The ID of the food item.

        Returns:
            FoodItem: The food item model.
        """
        item: FoodItem | None = (
            await self.db.execute(
                select(FoodItem).where(FoodItem.id == item_id)
            )
        ).scalar_one_or_none()

        if item is None:
            raise ItemNotFoundError(item_id)

        return item

    async def list_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,line-too-long  # noqa: E501
        self,
        name: str | None = None,
        category: FoodCategory | None = None,
        expiration_status: ExpirationStatus | None = None,
        expiring_within_days: int | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "expiration_asc",
    ) -> FoodItemListResponse:
        """List food items with optional filters and pagination.

        Args:
            name (str | None):
                Optional name filter.
            category (FoodCategory | None):
                Optional category filter.
            expiration_status (ExpirationStatus | None):
                Optional expiration status filter.
            expiring_within_days (int | None):
                Optional filter for items expiring within given days.
            page (int):
                Page number for pagination.
            page_size (int):
                Number of items per page.
            sort (str):
                Sorting option.

        Returns:
            FoodItemListResponse: The paginated list of food items.
        """
        query: Select[t.Tuple[FoodItem]] = select(FoodItem)

        # Apply filters
        if name is not None:
            query = query.where(FoodItem.name.ilike(f"%{name}%"))

        if category is not None:
            query = query.where(FoodItem.category == category)

        if expiring_within_days is not None:
            threshold_date: datetime = datetime.now(timezone.utc).replace(
                hour=23, minute=59, second=59
            )
            threshold_date = threshold_date + td(days=expiring_within_days)
            query = query.where(FoodItem.expiration_date <= threshold_date)

        # Get total count
        count_query: Select[t.Tuple[int]] = select(
            func.count()  # pylint: disable=not-callable
        ).select_from(query.subquery())
        total: int = (await self.db.execute(count_query)).scalar() or 0

        order_clause: UnaryExpression[t.Any] = FoodItem.expiration_date.asc()
        match sort:
            case "expiration_asc":
                order_clause = FoodItem.expiration_date.asc()
            case "expiration_desc":
                order_clause = FoodItem.expiration_date.desc()
            case "name_asc":
                order_clause = FoodItem.name.asc()
            case "name_desc":
                order_clause = FoodItem.name.desc()
            case "created_desc":
                order_clause = FoodItem.created_at.desc()
            case "created_asc":
                order_clause = FoodItem.created_at.asc()

        # Apply pagination
        offset: int = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(order_clause)

        items: t.Sequence[FoodItem] = (
            (await self.db.execute(query)).scalars().all()
        )

        # Convert to response schemas and filter by expiration status if needed
        item_responses: t.List[FoodItemResponse] = [
            self.convert_item_to_response(item) for item in items
        ]

        if expiration_status:
            item_responses = [
                item
                for item in item_responses
                if item.expiration_status == expiration_status
            ]
            total = len(item_responses)

        total_pages: int = (
            (total + page_size - 1) // page_size if total > 0 else 1
        )

        return FoodItemListResponse(
            items=item_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def create_item(  # pylint: disable=too-many-arguments,too-many-positional-arguments,line-too-long  # noqa: E501
        self,
        name: str,
        quantity: int,
        expiration_date: datetime,
        user_id: int,
        category: FoodCategory = FoodCategory.OTHER,
        description: str | None = None,
        image_base64: str | None = None,
        image_bytes: bytes | None = None,
        image_mime_type: str | None = None,
    ) -> FoodItemResponse:
        """Create a new food item.

        Args:
            name (str): The name of the food item.
            quantity (int): The quantity of the food item.
            expiration_date (datetime): The expiration date of the food item.
            user_id (int): The ID of the user creating the item.
            category (FoodCategory): The category of the food item.
            description (str | None): An optional description of the food item.
            image_base64 (str | None): An optional base64-encoded image string.
            image_bytes (bytes | None): An optional raw image data.
            image_mime_type (str | None): The MIME type of the image.

        Returns:
            FoodItemResponse: The created food item response schema.
        """
        new_item: FoodItem = FoodItem(
            name=name,
            quantity=quantity,
            expiration_date=expiration_date,
            category=category,
            description=description,
            created_by=user_id,
        )

        self.db.add(new_item)
        await self.db.flush()

        # Handle image if provided
        if image_base64 is not None:
            image_path, image_data, mime_type = await self.save_image_from_b64(
                image_base64, new_item.id
            )
            new_item.image_path = image_path
            new_item.image_data = image_data
            new_item.image_mime_type = mime_type
        elif image_bytes is not None:
            image_path, image_data, mime_type = self._process_image_data(
                image_bytes, new_item.id, image_mime_type
            )
            new_item.image_path = image_path
            new_item.image_data = image_data
            new_item.image_mime_type = mime_type

        # Flush again to persist image attributes before refresh
        await self.db.flush()
        await self.db.refresh(new_item)
        return self.convert_item_to_response(new_item)

    async def update_item(  # pylint: disable=too-many-arguments,too-many-positional-arguments,line-too-long  # noqa: E501
        self,
        item_id: int,
        name: str | None = None,
        quantity: int | None = None,
        expiration_date: datetime | None = None,
        category: FoodCategory | None = None,
        description: str | None = None,
        image_base64: str | None = None,
        image_bytes: bytes | None = None,
        image_mime_type: str | None = None,
        remove_image: bool = False,
    ) -> FoodItemResponse:
        """Update an existing food item.

        Args:
            item_id (int):
                The ID of the food item to update.
            name (str | None):
                The new name of the food item.
            quantity (int | None):
                The new quantity of the food item.
            expiration_date (datetime | None):
                The new expiration date.
            category (FoodCategory | None):
                The new category of the food item.
            description (str | None):
                The new description of the food item.
            image_base64 (str | None):
                An optional new base64-encoded image string.
            image_bytes (bytes | None):
                An optional new raw image data.
            image_mime_type (str | None):
                The MIME type of the new image.
            remove_image (bool):
                Whether to remove the existing image.

        Returns:
            FoodItemResponse: The updated food item response schema.
        """
        item: FoodItem = await self.get_item_model(item_id)

        # Update fields if provided
        if name is not None:
            item.name = name
        if quantity is not None:
            item.quantity = quantity
        if expiration_date is not None:
            item.expiration_date = expiration_date
        if category is not None:
            item.category = category
        if description is not None:
            item.description = description

        # Handle image removal
        if remove_image:
            self.delete_image_file(item.image_path)
            item.image_path = None
            item.image_data = None
            item.image_mime_type = None

        # Handle new image
        if image_base64:
            # Remove old image first
            self.delete_image_file(item.image_path)
            image_path, image_data, mime_type = await self.save_image_from_b64(
                image_base64, item.id
            )
            item.image_path = image_path
            item.image_data = image_data
            item.image_mime_type = mime_type
        elif image_bytes:
            self.delete_image_file(item.image_path)
            image_path, image_data, mime_type = self._process_image_data(
                image_bytes, item.id, image_mime_type
            )
            item.image_path = image_path
            item.image_data = image_data
            item.image_mime_type = mime_type

        # Flush to persist all changes (including image) before refresh
        await self.db.flush()
        await self.db.refresh(item)
        return self.convert_item_to_response(item)

    async def delete_item(self, item_id: int) -> None:
        """Delete a food item by ID.

        Args:
            item_id (int): The ID of the food item to delete.
        """
        item: FoodItem = await self.get_item_model(item_id)

        self.delete_image_file(item.image_path)

        await self.db.delete(item)

    async def get_expiration_alerts(self) -> ExpirationAlertSummary:
        """Get a summary of items with expiration alerts.

        Returns:
            ExpirationAlertSummary: The summary of expiration alerts.
        """
        items: t.Sequence[FoodItem] = (
            (await self.db.execute(select(FoodItem))).scalars().all()
        )

        expired_items: t.List[ExpirationAlert] = []
        critical_items: t.List[ExpirationAlert] = []
        warning_items: t.List[ExpirationAlert] = []

        for item in items:
            item_status: ExpirationStatus = item.get_expiration_status(
                SETTINGS.expiration_warning_days,
                SETTINGS.expiration_critical_days,
            )
            days: int = calculate_days_until_expiration(item.expiration_date)

            alert: ExpirationAlert = ExpirationAlert(
                item_id=item.id,
                item_name=item.name,
                expiration_date=item.expiration_date,
                days_until_expiration=days,
                status=item_status,
                quantity=item.quantity,
                category=item.category,
            )

            if item_status == ExpirationStatus.EXPIRED:
                expired_items.append(alert)
            elif item_status == ExpirationStatus.CRITICAL:
                critical_items.append(alert)
            elif item_status == ExpirationStatus.WARNING:
                warning_items.append(alert)

        return ExpirationAlertSummary(
            expired_count=len(expired_items),
            critical_count=len(critical_items),
            warning_count=len(warning_items),
            expired_items=expired_items,
            critical_items=critical_items,
            warning_items=warning_items,
        )

    async def get_statistics(self) -> FoodClosetStats:
        """Get overall statistics for the food closet.

        Returns:
            FoodClosetStats: The food closet statistics.
        """
        items: t.Sequence[FoodItem] = (
            (await self.db.execute(select(FoodItem))).scalars().all()
        )
        total_items: int = len(items)
        total_quantity: int = sum(item.quantity for item in items)

        # Count by category
        items_by_category: t.Dict[str, int] = {}
        for item in items:
            cat: str = item.category.value
            items_by_category[cat] = items_by_category.get(cat, 0) + 1

        # Count by expiration status
        expiration_summary: t.Dict[str, int] = {
            ExpirationStatus.FRESH.value: 0,
            ExpirationStatus.WARNING.value: 0,
            ExpirationStatus.CRITICAL.value: 0,
            ExpirationStatus.EXPIRED.value: 0,
        }

        items_expiring_soon: int = 0
        for item in items:
            item_status: ExpirationStatus = item.get_expiration_status(
                SETTINGS.expiration_warning_days,
                SETTINGS.expiration_critical_days,
            )
            expiration_summary[item_status.value] += 1
            if item_status in (
                ExpirationStatus.WARNING,
                ExpirationStatus.CRITICAL,
            ):
                items_expiring_soon += 1

        return FoodClosetStats(
            total_items=total_items,
            total_quantity=total_quantity,
            items_by_category=items_by_category,
            expiration_summary=expiration_summary,
            items_expiring_soon=items_expiring_soon,
        )
