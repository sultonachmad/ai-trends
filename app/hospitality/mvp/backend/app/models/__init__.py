"""Domain models — import every entity here so SQLModel registers its table metadata.

Add new models as:
    from app.models.my_entity import MyEntity, MyEntityCreate, MyEntityRead, MyEntityUpdate

Hospitality suite (see .ttest/contexts/database-design.md):
    app.models.control_plane  — tenants, routing, plans, entitlements (15 tables)
    app.models.tenant.<domain> — operational tenant data, domains A–T (128 tables)
Each package re-exports `<Entity>`, `<Entity>Create`, `<Entity>Read`, `<Entity>Update`.
"""

from app.models import control_plane, tenant
from app.models.control_plane import *  # noqa: F403
from app.models.sample_item import SampleItem, SampleItemCreate, SampleItemRead, SampleItemUpdate
from app.models.tenant import *  # noqa: F403

__all__ = [
    "SampleItem",
    "SampleItemCreate",
    "SampleItemRead",
    "SampleItemUpdate",
    *control_plane.__all__,
    *tenant.__all__,
]
