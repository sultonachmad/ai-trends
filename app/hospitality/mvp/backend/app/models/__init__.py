"""Domain models — import every entity here so SQLModel registers its table metadata.

Add new models as:
    from app.models.my_entity import MyEntity, MyEntityCreate, MyEntityRead, MyEntityUpdate
"""

from app.models.sample_item import SampleItem, SampleItemCreate, SampleItemRead, SampleItemUpdate

__all__ = [
    "SampleItem",
    "SampleItemCreate",
    "SampleItemRead",
    "SampleItemUpdate",
]
