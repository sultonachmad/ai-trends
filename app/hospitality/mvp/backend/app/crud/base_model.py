"""Shared base model and timestamp mixin for CRUD entities.

Every entity created with this prefab should extend `BaseEntity` (or, if a
different primary key shape is needed, just `TimestampMixin` directly) so
each table gets a consistent auto-increment `id`, `created_at`, and
`updated_at` column for free. See `AGENTS-be.md` in this prefab for the
step-by-step guide to defining a new entity.

No `from __future__ import annotations` here, and don't add it to entity
model files that declare a `Relationship()` field (scalar or collection) —
it breaks SQLAlchemy's class resolution for that field. See "Adding
Relationships Between Entities" in `AGENTS-be.md`.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Timezone-aware 'now', used as the default/onupdate value for timestamps."""
    return datetime.now(UTC)


def utc_datetime_field(
    *,
    default_now: bool = False,
    onupdate_now: bool = False,
    nullable: bool = False,
    **field_kwargs: object,
) -> object:
    """The one correct way to declare a custom `datetime` column on an entity.

    Every datetime column in this codebase is timezone-aware (Postgres
    `TIMESTAMP WITH TIME ZONE`, all values in UTC). Declaring a bare
    `datetime` field instead maps to `TIMESTAMP WITHOUT TIME ZONE`, which
    mixes offset-naive and offset-aware values on the same row and fails at
    INSERT/UPDATE with `can't subtract offset-naive and offset-aware
    datetimes`. Use this helper so that can't happen:

        class Event(BaseEntity, table=True):
            starts_at: datetime = utc_datetime_field(nullable=True)
            published_at: datetime = utc_datetime_field(default_now=True)

    - `default_now=True`  → server stamps `_utcnow()` at insert time.
    - `onupdate_now=True` → DB refreshes the value on every update.
    - `nullable=True`     → column allows NULL (pair with `datetime | None`).
    """
    extras: dict[str, object] = {}
    if onupdate_now:
        extras["sa_column_kwargs"] = {"onupdate": _utcnow}
    if default_now:
        extras["default_factory"] = _utcnow
    else:
        extras["default"] = None
    return Field(
        nullable=nullable,
        sa_type=DateTime(timezone=True),
        **extras,
        **field_kwargs,
    )


class TimestampMixin(SQLModel):
    """Adds `created_at`, `updated_at`, `created_by`, and `updated_by` columns.

    `created_at` is set once, at insert time, via `default_factory`.
    `updated_at` is set at insert time and then refreshed on every subsequent
    update by the database via `sa_column_kwargs={"onupdate": ...}`.

    `created_by` / `updated_by` are populated only when the router was built
    with `create_crud_router(..., current_user_dep=...)`. They stay NULL for
    anonymous writes — never make them non-nullable.
    """

    created_at: datetime = Field(
        default_factory=_utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True),
        description="When this record was created (UTC).",
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"onupdate": _utcnow},
        description="When this record was last updated (UTC).",
    )
    created_by: str | None = Field(
        default=None,
        nullable=True,
        description="Identifier of the user who created this record; NULL when anonymous.",
    )
    updated_by: str | None = Field(
        default=None,
        nullable=True,
        description="Identifier of the user who last updated this record; NULL when anonymous.",
    )


class BaseEntity(TimestampMixin, SQLModel):
    """Abstract base for CRUD entities: auto-increment `id` + timestamps.

    Subclass with `table=True` and add your own fields, e.g.:

        class Widget(BaseEntity, table=True):
            name: str
            description: str | None = None
    """

    id: int | None = Field(default=None, primary_key=True)
