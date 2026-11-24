"""The hourly guest ID purge runs at once, survives a failing tick, and stops when asked."""

import asyncio

import pytest

from app.services import id_retention


async def test_the_loop_purges_at_once_and_keeps_going_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = asyncio.Event()
    ticks: list[int] = []

    async def purge(factory, storage):  # noqa: ANN001, ANN202 — stands in for the real purge
        ticks.append(1)
        if len(ticks) == 1:
            raise RuntimeError("storage away")
        stop.set()

    monkeypatch.setattr(id_retention, "purge_expired_ids", purge)

    await asyncio.wait_for(id_retention.run_id_purge_loop(None, stop, interval_seconds=0), 5)

    assert len(ticks) == 2
