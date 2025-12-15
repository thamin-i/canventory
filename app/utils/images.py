"""Image utilities."""

import os

from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import FoodItem


async def get_food_item_image(
    item_id: int,
    db: AsyncSession,
) -> FileResponse | Response:
    """Retrieve the image for a food item.

    Args:
        item_id: The ID of the food item.
        db: The database session.

    Returns:
        FileResponse for filesystem images, Response for database-stored images.
    """
    item: FoodItem | None = (
        await db.execute(select(FoodItem).where(FoodItem.id == item_id))
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Food item with ID {item_id} not found",
        )

    if item.image_path and os.path.exists(item.image_path):
        return FileResponse(
            item.image_path,
            media_type=item.image_mime_type or "image/jpeg",
        )

    if item.image_data:
        return Response(
            content=item.image_data,
            media_type=item.image_mime_type or "image/jpeg",
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No image available for this item",
    )


def delete_image_file_from_filesystem(image_path: str | None) -> None:
    """Delete image file from filesystem.

    Args:
        image_path (str | None): Path to the image file.
    """
    if image_path is not None and os.path.exists(image_path):
        os.remove(image_path)
