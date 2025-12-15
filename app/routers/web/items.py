"""Web item CRUD routes."""

import typing as t
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_web_user
from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import FoodCategory, User
from app.services import ImageTooLargeError, ItemNotFoundError, ItemService
from app.services.item_service import FoodItemResponse
from app.utils.categories import get_categories
from app.utils.images import get_food_item_image

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/items/new", response_class=HTMLResponse, response_model=None)
async def new_item_page(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    name: str | None = None,
    category: str | None = None,
    barcode: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Render new item form.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        name (str | None): Optional prefill name.
        category (str | None): Optional prefill category.
        barcode (str | None): Optional barcode to include in description.

    Returns:
        RedirectResponse | HTMLResponse:
            The rendered new item form or a redirect to login.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    default_date: str = (datetime.now() + timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )
    prefill: t.Dict[str, str] = {
        "name": name or "",
        "category": category or "other",
        "description": f"Barcode: {barcode}" if barcode else "",
    }

    return TEMPLATES.TemplateResponse(
        "pages/item_form.html",
        {
            "request": request,
            "user": user,
            "item": None,
            "categories": await get_categories(db),
            "default_date": default_date,
            "prefill": prefill,
        },
    )


@ROUTER.post("/items/new", response_model=None)
async def create_item(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,line-too-long  # noqa: E501
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    name: str = Form(...),
    quantity: int = Form(...),
    category: str = Form("other"),
    expiration_date: str = Form(...),
    description: str | None = Form(None),
    image: UploadFile | None = File(None),
) -> RedirectResponse | HTMLResponse:
    """Handle new item form submission.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        name (str): The item name.
        quantity (int): The item quantity.
        category (str): The item category.
        expiration_date (str): The item expiration date as ISO string.
        description (str | None): The item description.
        image (UploadFile | None): Optional uploaded image file.

    Returns:
        RedirectResponse | HTMLResponse:
            A redirect to the dashboard on success,
            or the new item form with an error on failure.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        exp_date: datetime = datetime.fromisoformat(expiration_date)
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)
    except ValueError:
        default_date: str = (datetime.now() + timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        return TEMPLATES.TemplateResponse(
            "pages/item_form.html",
            {
                "request": request,
                "user": user,
                "item": None,
                "categories": await get_categories(db),
                "default_date": default_date,
                "error": "Invalid expiration date",
            },
        )

    # Read image data if provided
    image_bytes: bytes | None = None
    image_mime: str | None = None
    if image and image.filename:
        image_bytes = await image.read()
        image_mime = image.content_type

    try:
        await ItemService(db).create_item(
            name=name,
            quantity=quantity,
            expiration_date=exp_date,
            user_id=user.id,
            category=FoodCategory(category),
            description=description,
            image_bytes=image_bytes,
            image_mime_type=image_mime,
        )
    except ImageTooLargeError:
        default_date = (datetime.now() + timedelta(days=30)).strftime(
            "%Y-%m-%d"
        )
        return TEMPLATES.TemplateResponse(
            "pages/item_form.html",
            {
                "request": request,
                "user": user,
                "item": None,
                "categories": await get_categories(db),
                "default_date": default_date,
                "error": "Image is too large",
            },
        )

    return RedirectResponse(url="/web/dashboard", status_code=303)


@ROUTER.get(
    "/items/{item_id}/edit", response_class=HTMLResponse, response_model=None
)
async def edit_item_page(
    request: Request,
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse | HTMLResponse:
    """Render edit item form.

    Args:
        request (Request): The incoming request.
        item_id (int): The ID of the item to edit.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse | HTMLResponse:
             The rendered edit item form or a redirect to login.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        item_response: FoodItemResponse = await ItemService(db).get_item(
            item_id
        )
    except ItemNotFoundError:
        return RedirectResponse(url="/web/dashboard", status_code=303)

    item_dict: dict[str, t.Any] = item_response.model_dump()
    item_dict["expiration_date"] = item_response.expiration_date.isoformat()
    item_dict["category"] = item_response.category.value

    return TEMPLATES.TemplateResponse(
        "pages/item_form.html",
        {
            "request": request,
            "user": user,
            "item": item_dict,
            "categories": await get_categories(db),
            "default_date": None,
        },
    )


@ROUTER.post("/items/{item_id}/edit")
async def update_item(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,line-too-long  # noqa: E501
    request: Request,
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    name: str = Form(...),
    quantity: int = Form(...),
    category: str = Form("other"),
    expiration_date: str = Form(...),
    description: str | None = Form(None),
    image: UploadFile | None = File(None),
    remove_image: str | None = Form(None),
) -> RedirectResponse:
    """Handle edit item form submission.

    Args:
        request (Request): The incoming request.
        item_id (int): The ID of the item to edit.
        db (AsyncSession): The database session.
        name (str): The item name.
        quantity (int): The item quantity.
        category (str): The item category.
        expiration_date (str): The item expiration date as ISO string.
        description (str | None): The item description.
        image (UploadFile | None): Optional uploaded image file.
        remove_image (str | None): Flag to remove existing image.

    Returns:
        RedirectResponse:
            A redirect to the dashboard after processing.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        exp_date: datetime = datetime.fromisoformat(expiration_date)
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)
    except ValueError:
        return RedirectResponse(
            url=f"/web/items/{item_id}/edit", status_code=303
        )

    # Read image data if provided
    image_bytes: bytes | None = None
    image_mime: str | None = None
    if image and image.filename:
        image_bytes = await image.read()
        image_mime = image.content_type

    try:
        await ItemService(db).update_item(
            item_id=item_id,
            name=name,
            quantity=quantity,
            expiration_date=exp_date,
            category=FoodCategory(category),
            description=description,
            image_bytes=image_bytes,
            image_mime_type=image_mime,
            remove_image=bool(remove_image),
        )
    except ItemNotFoundError:
        return RedirectResponse(url="/web/dashboard", status_code=303)
    except ImageTooLargeError:
        return RedirectResponse(
            url=f"/web/items/{item_id}/edit", status_code=303
        )

    return RedirectResponse(url="/web/dashboard", status_code=303)


@ROUTER.post("/items/{item_id}/delete")
async def delete_item(
    request: Request,
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Handle item deletion.

    Args:
        request (Request): The incoming request.
        item_id (int): The ID of the item to delete.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse:
            A redirect to the dashboard after deletion.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await ItemService(db).delete_item(item_id)
    except ItemNotFoundError:
        pass  # Item already deleted, just redirect

    return RedirectResponse(url="/web/dashboard", status_code=303)


@ROUTER.get("/items/{item_id}/image", response_model=None)
async def get_item_image(
    request: Request,
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse | Response:
    """Get the image for a food item.

    Args:
        request (Request): The incoming request.
        item_id (int): The ID of the item whose image to retrieve.
        db (AsyncSession): The database session.

    Returns:
        FileResponse | Response:
            The image file response or a 404 response if not found.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return await get_food_item_image(item_id, db)
