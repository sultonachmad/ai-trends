"""The tenant change history is chained: an edited or missing entry shows up."""

import datetime as dt
import uuid

from app.audit.service import compute_entry_hash
from app.models.tenant import TenantAuditEntry
from app.services.tenant_audit import _pinned, verify

TENANT = uuid.uuid4()


def _chain(length: int) -> list[TenantAuditEntry]:
    entries: list[TenantAuditEntry] = []
    for number in range(length):
        entry = TenantAuditEntry(
            tenant_id=TENANT,
            property_id=uuid.uuid4(),
            event_id=f"channel.connection.step{number}",
            actor_id="7",
            occurred_at=dt.datetime(2026, 11, 20, 8, number, tzinfo=dt.UTC),
            entity_table="channelconnection",
            entity_id=uuid.uuid4(),
            payload={"n": number},
            prev_hash=entries[-1].entry_hash if entries else None,
            entry_hash="",
        )
        entry.entry_hash = compute_entry_hash(entry.prev_hash, _pinned(entry))
        entries.append(entry)
    return entries


def test_an_untouched_chain_verifies() -> None:
    assert verify(_chain(4))
    assert verify([])


def test_an_edited_entry_breaks_the_chain() -> None:
    entries = _chain(3)
    entries[1].payload = {"n": 99}

    assert not verify(entries)


def test_a_changed_actor_or_time_breaks_the_chain() -> None:
    by_actor, by_time = _chain(2), _chain(2)
    by_actor[0].actor_id = "8"
    by_time[1].occurred_at += dt.timedelta(seconds=1)

    assert not verify(by_actor)
    assert not verify(by_time)


def test_a_removed_or_reordered_entry_breaks_the_chain() -> None:
    entries = _chain(4)

    assert not verify([entries[0], entries[2], entries[3]])
    assert not verify([entries[1], entries[0], entries[2], entries[3]])


def test_the_hash_covers_the_time_in_utc_whatever_zone_it_is_given_in() -> None:
    [entry] = _chain(1)
    jakarta = dt.timezone(dt.timedelta(hours=7))
    entry.occurred_at = entry.occurred_at.astimezone(jakarta)

    assert verify([entry])
