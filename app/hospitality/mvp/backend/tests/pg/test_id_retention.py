"""Guest ID images go 7 days after the stay; numbers after their retention date."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.documents.storage import DocumentStorage
from app.services.calendar_dates import property_today
from app.services.id_retention import purge_expired_ids
from tests.pg.conftest import (
    confirm_main_guest_id,
    image,
    make_booking,
    make_rate_plan,
    make_room_type,
    start_workspace,
)

pytestmark = pytest.mark.integration

DESK = "/api/front-desk"


async def _setup(client, nights: int = 2, **booking_fields) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=2, max_guests=4)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    booking = await make_booking(
        client,
        room,
        plan,
        today.isoformat(),
        (today + dt.timedelta(days=nights)).isoformat(),
        **booking_fields,
    )
    return {
        "tenant": workspace["tenant"]["id"],
        "room": room,
        "plan": plan,
        "today": today,
        "departure": today + dt.timedelta(days=nights),
        "booking": booking,
    }


def _url(ctx: dict, tail: str = "") -> str:
    return f"/api/bookings/{ctx['booking']['id']}/guests{tail}"


async def _scan(client, ctx, seed: str = "a") -> str:
    response = await client.post(
        _url(ctx, "/scan"),
        files={"file": ("ktp.jpg", image(seed), "image/jpeg")},
        data={"doc_type": "ktp"},
    )
    assert response.status_code == 201, response.text
    return response.json()["scan_id"]


async def _confirmed_with_photo(client, ctx) -> dict:
    scan_id = await _scan(client, ctx)
    body = await confirm_main_guest_id(client, ctx["booking"]["id"], scan_id=scan_id)
    return {"scan_id": scan_id, "document_id": body["guests"][0]["document"]["id"]}


async def _scan_row(session, scan_id: str):
    return (
        await session.execute(
            text("SELECT retention_until, purged_at FROM document WHERE id = :d"), {"d": scan_id}
        )
    ).one()


async def _purge(factory, day: dt.date):
    return await purge_expired_ids(factory, DocumentStorage(), today=day)


def _files(folder) -> list:
    return [path for path in folder.rglob("*") if path.is_file()]


async def test_the_image_is_kept_until_7_days_after_departure(
    pg_client, pg_session, pg_session_factory, _document_storage
) -> None:
    ctx = await _setup(pg_client)
    ids = await _confirmed_with_photo(pg_client, ctx)
    until = ctx["departure"] + dt.timedelta(days=7)

    assert (await _scan_row(pg_session, ids["scan_id"]))[0] == until
    await _purge(pg_session_factory, until)
    assert _files(_document_storage)
    await _purge(pg_session_factory, until + dt.timedelta(days=1))

    assert (await _scan_row(pg_session, ids["scan_id"]))[1] is not None
    assert _files(_document_storage) == []
    body = (await pg_client.get(_url(ctx))).json()
    assert body["guests"][0]["document"]["has_image"] is False
    assert body["main_guest_ready"] is True  # the confirmed number stays
    gone = await pg_client.get(_url(ctx, f"/documents/{ids['document_id']}/image"))
    assert (gone.status_code, gone.json()["detail"]["code"]) == (410, "id_image_gone")


async def test_a_photo_nobody_confirms_goes_the_next_day(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client)
    scan_id = await _scan(pg_client, ctx)

    await _purge(pg_session_factory, ctx["today"] + dt.timedelta(days=2))

    assert (await _scan_row(pg_session, scan_id))[1] is not None


async def test_a_replaced_photo_goes_at_the_next_run(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client)
    first = await _confirmed_with_photo(pg_client, ctx)
    second = await _scan(pg_client, ctx, seed="b")
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"], scan_id=second)

    await _purge(pg_session_factory, ctx["today"])

    assert (await _scan_row(pg_session, first["scan_id"]))[1] is not None
    assert (await _scan_row(pg_session, second))[1] is None


async def test_check_out_brings_image_deletion_forward(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, nights=10)
    ids = await _confirmed_with_photo(pg_client, ctx)
    line = (
        await pg_session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"),
            {"b": ctx["booking"]["id"]},
        )
    ).scalar_one()
    unit = ctx["room"]["units"][0]["id"]
    assert (await pg_client.put(f"{DESK}/lines/{line}/room", json={"unit_id": unit})).is_success
    url = f"{DESK}/bookings/{ctx['booking']['id']}"
    assert (await pg_client.post(f"{url}/check-in", json={})).status_code == 200
    out = await pg_client.post(
        f"{url}/check-out", json={"early": "keep_price", "leave_unpaid_reason": "Bayar nanti"}
    )
    assert out.status_code == 200, out.text

    assert (await _scan_row(pg_session, ids["scan_id"]))[0] == ctx["today"] + dt.timedelta(days=7)


async def test_cancelling_brings_image_deletion_forward(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, nights=10)
    ids = await _confirmed_with_photo(pg_client, ctx)

    cancelled = await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/cancel", json={"reason": "Batal"}
    )

    assert cancelled.status_code == 200, cancelled.text
    assert (await _scan_row(pg_session, ids["scan_id"]))[0] == ctx["today"] + dt.timedelta(days=7)


async def test_numbers_are_cleared_after_the_retention_date(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client)
    ids = await _confirmed_with_photo(pg_client, ctx)
    until = ctx["departure"] + dt.timedelta(days=730)

    done = await _purge(pg_session_factory, until + dt.timedelta(days=1))

    assert done.numbers >= 1
    row = (
        await pg_session.execute(
            text(
                "SELECT doc_number_encrypted, doc_number_hash, doc_number_last4, verified_at "
                "FROM guestdocument WHERE id = :d"
            ),
            {"d": ids["document_id"]},
        )
    ).one()
    assert row[:3] == (None, None, None)
    assert row[3] is not None
    body = (await pg_client.get(_url(ctx))).json()
    document = body["guests"][0]["document"]
    assert (document["masked_number"], document["usable"]) == (None, False)
    assert body["main_guest_ready"] is False
    reveal = await pg_client.post(_url(ctx, f"/documents/{ids['document_id']}/reveal"))
    assert (reveal.status_code, reveal.json()["detail"]["code"]) == (410, "id_number_cleared")


async def test_numbers_inside_their_retention_period_stay(
    pg_client, pg_session, pg_session_factory
) -> None:
    ctx = await _setup(pg_client)
    ids = await _confirmed_with_photo(pg_client, ctx)

    await _purge(pg_session_factory, ctx["departure"] + dt.timedelta(days=730))

    kept = await pg_session.execute(
        text("SELECT doc_number_encrypted IS NOT NULL FROM guestdocument WHERE id = :d"),
        {"d": ids["document_id"]},
    )
    assert kept.scalar_one() is True


async def test_a_guest_still_staying_elsewhere_keeps_the_photo(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client, nights=10, guest_phone="+6281234567890")
    ids = await _confirmed_with_photo(pg_client, ctx)
    later = ctx["today"] + dt.timedelta(days=20)
    await make_booking(
        pg_client,
        ctx["room"],
        ctx["plan"],
        later.isoformat(),
        (later + dt.timedelta(days=2)).isoformat(),
        guest_phone="+6281234567890",
    )

    cancelled = await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/cancel", json={"reason": "Batal"}
    )

    assert cancelled.status_code == 200, cancelled.text
    kept = (await _scan_row(pg_session, ids["scan_id"]))[0]
    assert kept == ctx["departure"] + dt.timedelta(days=7)


async def test_confirming_again_for_a_later_stay_keeps_the_photo_longer(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client, guest_phone="+6281234567890")
    ids = await _confirmed_with_photo(pg_client, ctx)
    later = ctx["today"] + dt.timedelta(days=5)
    second = await make_booking(
        pg_client,
        ctx["room"],
        ctx["plan"],
        later.isoformat(),
        (later + dt.timedelta(days=3)).isoformat(),
        guest_phone="+6281234567890",
    )

    await confirm_main_guest_id(pg_client, second["id"])

    kept = (await _scan_row(pg_session, ids["scan_id"]))[0]
    assert kept == later + dt.timedelta(days=3 + 7)
