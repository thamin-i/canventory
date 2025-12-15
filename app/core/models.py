"""SQLAlchemy database models."""

import enum
import typing as t
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.dates import calculate_days_until_expiration


class FoodCategory(str, enum.Enum):
    """Categories for food items."""

    CANNED_VEGETABLES = "canned_vegetables"
    CANNED_FRUITS = "canned_fruits"
    CANNED_MEATS = "canned_meats"
    CANNED_SOUPS = "canned_soups"
    GRAINS = "grains"
    PASTA = "pasta"
    RICE = "rice"
    CEREALS = "cereals"
    BEANS = "beans"
    NUTS = "nuts"
    DRIED_FRUITS = "dried_fruits"
    CONDIMENTS = "condiments"
    OILS = "oils"
    BAKING = "baking"
    SNACKS = "snacks"
    BEVERAGES = "beverages"
    BABY_FOOD = "baby_food"
    PET_FOOD = "pet_food"
    OTHER = "other"


class ExpirationStatus(str, enum.Enum):
    """Expiration status for food items."""

    FRESH = "fresh"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"


class User(Base):  # pylint: disable=too-few-public-methods
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    email_notifications_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )

    # Relationships
    food_items: Mapped[t.List["FoodItem"]] = relationship(
        "FoodItem", back_populates="created_by_user", lazy="selectin"
    )


class SystemSettings(Base):  # pylint: disable=too-few-public-methods
    """System settings model for application-wide configuration."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )


class Category(Base):  # pylint: disable=too-few-public-methods
    """Category model for food item categories."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    value: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )


class FoodItem(Base):  # pylint: disable=too-few-public-methods
    """Food item model."""

    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expiration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    category: Mapped[FoodCategory] = mapped_column(
        Enum(FoodCategory), nullable=False, default=FoodCategory.OTHER
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Image storage options
    image_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # For filesystem storage
    image_data: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )  # For database storage
    image_mime_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # Tracking
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
    )

    # Relationships
    created_by_user: Mapped["User"] = relationship(
        "User", back_populates="food_items"
    )

    def get_expiration_status(
        self, warning_days: int = 7, critical_days: int = 3
    ) -> ExpirationStatus:
        """Determine the expiration status of the food item.

        Args:
            warning_days (int, optional):
                Number of days before expiration to consider as warning.
                Defaults to 7.
            critical_days (int, optional):
                Number of days before expiration to consider as critical.
                Defaults to 3.

        Returns:
            ExpirationStatus:
                The expiration status of the food item.
        """
        match calculate_days_until_expiration(self.expiration_date):
            case d if d < 0:
                return ExpirationStatus.EXPIRED
            case d if d <= critical_days:
                return ExpirationStatus.CRITICAL
            case d if d <= warning_days:
                return ExpirationStatus.WARNING
            case _:
                return ExpirationStatus.FRESH
