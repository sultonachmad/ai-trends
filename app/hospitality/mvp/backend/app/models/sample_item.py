"""SampleItem entity — a general-purpose CRUD entity wired to the DB.

This is the sample entity that ships with the prefab. Copy this file and
rename `SampleItem` to your own domain entity (e.g. `Product`, `Task`, `Order`).
Update `app/models/__init__.py`, create `app/routers/<entity>.py`, and add
an Alembic migration.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.crud.base_model import BaseEntity, utc_datetime_field


class SampleItem(BaseEntity, table=True):
    """A generic sample item stored in the database."""

    name: str = Field(
        max_length=200,
        index=True,
        description="Short display name for the item.",
    )
    description: str | None = Field(
        default=None,
        nullable=True,
        description="Optional longer description.",
    )
    status: str = Field(
        default="active",
        description="active or archived",
    )
    due_at: datetime | None = utc_datetime_field(  # type: ignore[assignment]
        nullable=True,
        description="Optional deadline (UTC). Use utc_datetime_field for all datetime columns.",
    )


class SampleItemCreate(SQLModel):
    """Fields accepted when creating a SampleItem."""

    name: str
    description: str | None = None
    status: str = "active"
    due_at: datetime | None = None


class SampleItemUpdate(SQLModel):
    """Fields accepted when patching a SampleItem (all optional)."""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class SampleItemRead(SQLModel):
    """Fields returned when reading a SampleItem."""

    id: int
    name: str
    description: str | None
    status: str
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None
