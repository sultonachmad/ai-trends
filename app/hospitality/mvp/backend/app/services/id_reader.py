"""Reading fields off an ID image.

No real reader is approved for identity data yet (PRD open question), so there are two:

* the **simulated reader** (`PREFAB_ID_READER_SIMULATOR_ENABLED`, development only)
  returns fixed sample fields, clearly marked as simulated, whatever the image shows;
* the **manual reader** returns nothing: staff type the fields from the document.

Either way staff check every field before saving. A provider plugs in by implementing
`IdReader` and being returned from `get_id_reader`.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.services.id_validation import KTP

log = logging.getLogger(__name__)

if settings.ID_READER_SIMULATOR_ENABLED:
    log.warning(
        "ID reader SIMULATOR is ENABLED (PREFAB_ID_READER_SIMULATOR_ENABLED): guest ID photos "
        "are answered with sample fields. Development only."
    )


@dataclass(frozen=True)
class ReadFields:
    """What a reader thinks the document says. Every field may be missing."""

    number: str | None = None
    full_name: str | None = None
    birth_date: dt.date | None = None
    gender: str | None = None
    nationality: str | None = None
    expires_on: dt.date | None = None
    visa_type: str | None = None
    entry_date: dt.date | None = None


class IdReader(Protocol):
    name: str
    simulated: bool

    async def read(self, doc_type: str, image: bytes, today: dt.date) -> ReadFields: ...


class ManualReader:
    """No reading: the form starts empty."""

    name = "manual"
    simulated = False

    async def read(self, doc_type: str, image: bytes, today: dt.date) -> ReadFields:
        return ReadFields()


class SimulatedReader:
    """Sample fields for development. They describe nobody and must never be confirmed."""

    name = "simulated"
    simulated = True

    async def read(self, doc_type: str, image: bytes, today: dt.date) -> ReadFields:
        if doc_type == KTP:
            return ReadFields(
                number="3171234501900001",
                full_name="CONTOH SIMULASI",
                birth_date=dt.date(1990, 1, 5),
                gender="female",
                nationality="ID",
            )
        return ReadFields(
            number="X1234567",
            full_name="SAMPLE SIMULATED",
            birth_date=dt.date(1988, 7, 2),
            gender="male",
            nationality="AU",
            expires_on=today.replace(year=today.year + 5, day=1),
            visa_type="voa",
            entry_date=today,
        )


def get_id_reader() -> IdReader:
    """The reader in use (FastAPI dependency, so tests can swap it)."""
    return SimulatedReader() if settings.ID_READER_SIMULATOR_ENABLED else ManualReader()
