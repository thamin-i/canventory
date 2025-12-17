"""Image utilities."""

import hashlib
import os
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.globals import THUMBNAIL_DIR, THUMBNAIL_QUALITY, THUMBNAIL_SIZE
from app.core.models import FoodItem


def _generate_thumbnail_path(item_id: int, original_path: str | None) -> Path:
    """Generate a unique thumbnail path
        based on item ID and original image path.

    Args:
        item_id (int): The ID of the food item.
        original_path (str | None): The original image path.

    Returns:
        Path: The path to the thumbnail image.
    """
    hash_input: str = f"{item_id}_{original_path or 'db'}"
    hash_suffix: str = hashlib.md5(hash_input.encode()).hexdigest()[:8]
    return THUMBNAIL_DIR / f"thumb_{item_id}_{hash_suffix}.webp"


def _generate_thumbnail(image_data: bytes) -> bytes:
    """Generate a thumbnail from image data.

    Args:
        image_data (bytes): The original image data.

    Returns:
        bytes: The thumbnail image data in WebP format.
    """
    with Image.open(BytesIO(image_data)) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        output: BytesIO = BytesIO()
        img.save(
            output, format="WEBP", quality=THUMBNAIL_QUALITY, optimize=True
        )
        return output.getvalue()


async def get_food_item_image(
    item_id: int,
    db: AsyncSession,
    home_id: int | None = None,
    thumbnail: bool = False,
) -> FileResponse | Response:
    """Retrieve the image or thumbnail for a food item.

    Args:
        item_id (int):
            The ID of the food item.
        db (AsyncSession):
            The database session.
        home_id (int | None):
            The home ID to scope the query (optional, for access control).
        thumbnail (bool, optional):
            Whether to return a thumbnail version. Defaults to False.

    Returns:
        FileResponse | Response: The image response.
    """
    query = select(FoodItem).where(FoodItem.id == item_id)
    if home_id is not None:
        query = query.where(FoodItem.home_id == home_id)

    item: FoodItem | None = (await db.execute(query)).scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Food item with ID {item_id} not found",
        )

    # Cache headers for browser caching (1 week)
    cache_headers = {
        "Cache-Control": "public, max-age=604800, immutable",
        "Vary": "Accept",
    }

    if thumbnail:
        thumbnail_path: Path = _generate_thumbnail_path(
            item_id, item.image_path
        )

        if thumbnail_path.exists():
            return FileResponse(
                thumbnail_path,
                media_type="image/webp",
                headers=cache_headers,
            )

        original_data: bytes | None = None

        if item.image_path and os.path.exists(item.image_path):
            with open(item.image_path, "rb") as f:
                original_data = f.read()
        elif item.image_data:
            original_data = item.image_data

        if original_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No image available for this item",
            )

        thumbnail_data: bytes = _generate_thumbnail(original_data)
        with open(thumbnail_path, "wb") as f:
            f.write(thumbnail_data)

        return Response(
            content=thumbnail_data,
            media_type="image/webp",
            headers=cache_headers,
        )

    if item.image_path and os.path.exists(item.image_path):
        return FileResponse(
            item.image_path,
            media_type=item.image_mime_type or "image/jpeg",
            headers=cache_headers,
        )

    if item.image_data:
        return Response(
            content=item.image_data,
            media_type=item.image_mime_type or "image/jpeg",
            headers=cache_headers,
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


def delete_thumbnail(item_id: int, image_path: str | None) -> None:
    """Delete the thumbnail file for a given food item.

    Args:
        item_id (int): The ID of the food item.
        image_path (str | None): The original image path.
    """
    thumbnail_path: Path = _generate_thumbnail_path(item_id, image_path)
    if thumbnail_path.exists():
        thumbnail_path.unlink()
