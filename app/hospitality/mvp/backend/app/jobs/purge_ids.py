"""Delete guest ID images after the stay and ID numbers after their retention date.

    cd backend && python -m app.jobs.purge_ids

Safe to run as often as you like; it only touches records whose date has passed.
"""

import asyncio
import logging

from app.database import async_session_factory, engine
from app.documents.storage import DocumentStorage
from app.services.id_retention import Purged, purge_expired_ids

log = logging.getLogger(__name__)


async def main() -> Purged:
    try:
        return await purge_expired_ids(async_session_factory, DocumentStorage())
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    done = asyncio.run(main())
    log.info("Deleted %d image(s) and %d number(s)", done.images, done.numbers)
