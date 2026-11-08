"""User table for credentials-based (email/password) authentication."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(
        default_factory=_utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
