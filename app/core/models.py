"""SQLAlchemy database models."""

import enum
import typing as t
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.dates import calculate_days_until_expiration


class ExpirationStatus(str, enum.Enum):
    """Expiration status for food items."""

    FRESH = "fresh"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"


class HomeMemberRole(str, enum.Enum):
    """Role of a user in a home."""

    OWNER = "owner"
    MEMBER = "member"


class HomeMembershipStatus(str, enum.Enum):
    """Status of a home membership/invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"


class Home(Base):  # pylint: disable=too-few-public-methods
    """Home model - a household that contains food items and categories."""

    __tablename__ = "homes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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
    owner: Mapped["User"] = relationship(
        "User", back_populates="owned_home", foreign_keys=[owner_id]
    )
    members: Mapped[t.List["HomeMembership"]] = relationship(
        "HomeMembership", back_populates="home", cascade="all, delete-orphan"
    )
    categories: Mapped[t.List["Category"]] = relationship(
        "Category", back_populates="home", cascade="all, delete-orphan"
    )
    storage_locations: Mapped[t.List["StorageLocation"]] = relationship(
        "StorageLocation", back_populates="home", cascade="all, delete-orphan"
    )
    food_items: Mapped[t.List["FoodItem"]] = relationship(
        "FoodItem", back_populates="home", cascade="all, delete-orphan"
    )


class HomeMembership(Base):  # pylint: disable=too-few-public-methods
    """Association table for users belonging to homes."""

    __tablename__ = "home_memberships"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    home_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homes.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[HomeMemberRole] = mapped_column(
        Enum(HomeMemberRole), nullable=False, default=HomeMemberRole.MEMBER
    )
    status: Mapped[HomeMembershipStatus] = mapped_column(
        Enum(HomeMembershipStatus),
        nullable=False,
        default=HomeMembershipStatus.PENDING,
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("home_id", "user_id", name="uq_home_membership"),
    )

    # Relationships
    home: Mapped["Home"] = relationship("Home", back_populates="members")
    user: Mapped["User"] = relationship(
        "User", back_populates="home_memberships"
    )


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
    current_home_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("homes.id", ondelete="SET NULL"), nullable=True
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
    owned_home: Mapped["Home | None"] = relationship(
        "Home",
        back_populates="owner",
        foreign_keys="Home.owner_id",
        uselist=False,
    )
    current_home: Mapped["Home | None"] = relationship(
        "Home", foreign_keys=[current_home_id]
    )
    home_memberships: Mapped[t.List["HomeMembership"]] = relationship(
        "HomeMembership", back_populates="user", cascade="all, delete-orphan"
    )
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
    """Category model for food item categories (home-specific)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    home_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homes.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )

    __table_args__ = (
        UniqueConstraint("home_id", "value", name="uq_category_home_value"),
        Index("ix_categories_home_id", "home_id"),
    )

    # Relationships
    home: Mapped["Home"] = relationship("Home", back_populates="categories")


class StorageLocation(Base):  # pylint: disable=too-few-public-methods
    """Storage location model for where items are stored (home-specific)."""

    __tablename__ = "storage_locations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    home_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homes.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
    )

    __table_args__ = (
        UniqueConstraint(
            "home_id", "name", name="uq_storage_location_home_name"
        ),
        Index("ix_storage_locations_home_id", "home_id"),
    )

    # Relationships
    home: Mapped["Home"] = relationship(
        "Home", back_populates="storage_locations"
    )
    food_items: Mapped[t.List["FoodItem"]] = relationship(
        "FoodItem", back_populates="storage_location"
    )


class FoodItem(Base):  # pylint: disable=too-few-public-methods
    """Food item model (home-specific)."""

    __tablename__ = "food_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    home_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("homes.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expiration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other"
    )
    location_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("storage_locations.id", ondelete="SET NULL"),
        nullable=True,
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

    __table_args__ = (Index("ix_food_items_home_id", "home_id"),)

    # Relationships
    home: Mapped["Home"] = relationship("Home", back_populates="food_items")
    storage_location: Mapped["StorageLocation | None"] = relationship(
        "StorageLocation", back_populates="food_items"
    )
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
