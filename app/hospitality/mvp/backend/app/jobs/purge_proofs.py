"""Delete transfer-proof images past their retention period.

    cd backend && python -m app.jobs.purge_proofs

Safe to run as often as you like; it only touches files whose date has passed.
"""

import asyncio
import logging

from app.database import async_session_factory, engine
from app.documents.storage import DocumentStorage
from app.services.proof_retention import purge_expired_proofs

log = logging.getLogger(__name__)


async def main() -> int:
    try:
        return await purge_expired_proofs(async_session_factory, DocumentStorage())
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("Deleted %d image(s)", asyncio.run(main()))
