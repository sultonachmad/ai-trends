"""Daily full re-sync of every live channel connection.

Run from a scheduler, e.g. once a night:

    python -m app.jobs.sync_channels

Queues the whole selling window for every live or paused connection and pushes until
acknowledged or a failure waits out its backoff. Paused connections are sent as
closed everywhere, which also refreshes their last-success time.
"""

import asyncio
import logging

from app.database import async_session_factory
from app.services.channel_push import process_due

log = logging.getLogger(__name__)


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    pushed = await process_due(async_session_factory)
    log.info("Channel sync finished (%d push(es) acknowledged)", pushed)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
