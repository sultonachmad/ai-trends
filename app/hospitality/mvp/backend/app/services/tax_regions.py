"""Starter regions for hotel tax (PBJT jasa perhotelan).

The suggested rate is the legal maximum (UU HKPD 1/2022 caps PBJT at 10%). None of these
values is verified for a specific regency or city: the owner must check them with their
regional tax office (Bapenda) and confirm before any tax is charged.
"""

from dataclasses import dataclass
from decimal import Decimal

OTHER = "other"
PBJT_MAX = Decimal("10")
SERVICE_MAX = Decimal("15")


@dataclass(frozen=True)
class Region:
    code: str  # kabupaten/kota code (Kemendagri)
    name: str
    province: str
    suggested_pbjt_pct: Decimal


REGIONS: tuple[Region, ...] = (
    Region("51.03", "Kabupaten Badung", "Bali", PBJT_MAX),
    Region("51.71", "Kota Denpasar", "Bali", PBJT_MAX),
    Region("51.04", "Kabupaten Gianyar", "Bali", PBJT_MAX),
    Region("31.71", "Kota Jakarta Pusat", "DKI Jakarta", PBJT_MAX),
    Region("31.72", "Kota Jakarta Utara", "DKI Jakarta", PBJT_MAX),
    Region("31.73", "Kota Jakarta Barat", "DKI Jakarta", PBJT_MAX),
    Region("31.74", "Kota Jakarta Selatan", "DKI Jakarta", PBJT_MAX),
    Region("31.75", "Kota Jakarta Timur", "DKI Jakarta", PBJT_MAX),
    Region("34.71", "Kota Yogyakarta", "DI Yogyakarta", PBJT_MAX),
    Region("34.04", "Kabupaten Sleman", "DI Yogyakarta", PBJT_MAX),
    Region("32.73", "Kota Bandung", "Jawa Barat", PBJT_MAX),
    Region("35.78", "Kota Surabaya", "Jawa Timur", PBJT_MAX),
    Region(OTHER, "Other region", "", PBJT_MAX),
)
REGION_CODES = frozenset(region.code for region in REGIONS)
