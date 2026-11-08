"""Tenant database — A. Organisation & property."""

from app.models.tenant.organisation.amenity import (
    Amenity,
    AmenityCreate,
    AmenityRead,
    AmenityUpdate,
)
from app.models.tenant.organisation.channel import (
    Channel,
    ChannelCreate,
    ChannelRead,
    ChannelUpdate,
)
from app.models.tenant.organisation.document import (
    Document,
    DocumentCreate,
    DocumentRead,
    DocumentUpdate,
)
from app.models.tenant.organisation.legal_entity import (
    LegalEntity,
    LegalEntityCreate,
    LegalEntityRead,
    LegalEntityUpdate,
)
from app.models.tenant.organisation.market_segment import (
    MarketSegment,
    MarketSegmentCreate,
    MarketSegmentRead,
    MarketSegmentUpdate,
)
from app.models.tenant.organisation.property import (
    Property,
    PropertyCreate,
    PropertyRead,
    PropertyUpdate,
)
from app.models.tenant.organisation.property_area import (
    PropertyArea,
    PropertyAreaCreate,
    PropertyAreaRead,
    PropertyAreaUpdate,
)
from app.models.tenant.organisation.reason_code import (
    ReasonCode,
    ReasonCodeCreate,
    ReasonCodeRead,
    ReasonCodeUpdate,
)
from app.models.tenant.organisation.tenant_profile import (
    TenantProfile,
    TenantProfileCreate,
    TenantProfileRead,
    TenantProfileUpdate,
)

__all__ = [
    "TenantProfile",
    "TenantProfileCreate",
    "TenantProfileRead",
    "TenantProfileUpdate",
    "LegalEntity",
    "LegalEntityCreate",
    "LegalEntityRead",
    "LegalEntityUpdate",
    "Property",
    "PropertyCreate",
    "PropertyRead",
    "PropertyUpdate",
    "PropertyArea",
    "PropertyAreaCreate",
    "PropertyAreaRead",
    "PropertyAreaUpdate",
    "Amenity",
    "AmenityCreate",
    "AmenityRead",
    "AmenityUpdate",
    "Document",
    "DocumentCreate",
    "DocumentRead",
    "DocumentUpdate",
    "Channel",
    "ChannelCreate",
    "ChannelRead",
    "ChannelUpdate",
    "MarketSegment",
    "MarketSegmentCreate",
    "MarketSegmentRead",
    "MarketSegmentUpdate",
    "ReasonCode",
    "ReasonCodeCreate",
    "ReasonCodeRead",
    "ReasonCodeUpdate",
]
