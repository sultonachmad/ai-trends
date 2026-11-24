"""Guest IDs: capture, confirm, masked reads, logged reveals, access and check-in."""

import datetime as dt

import pytest
from sqlalchemy import text

from app.config import settings
from app.services.calendar_dates import property_today
from tests.pg.conftest import (
    KTP_FIELDS,
    add_staff_member,
    confirm_main_guest_id,
    image,
    make_booking,
    make_rate_plan,
    make_room_type,
    start_workspace,
)
from tests.pg.test_feature_access import _give_role

pytestmark = pytest.mark.integration

DESK = "/api/front-desk"
PHOTO = image("ktp-photo")


def _passport(**overrides) -> dict:
    today = overrides.pop("today")
    return {
        "doc_type": "passport",
        "number": "PA1234567",
        "full_name": "Anna Schmidt",
        "birth_date": "1988-07-02",
        "gender": "female",
        "nationality": "DE",
        "expires_on": today.replace(year=today.year + 3).isoformat(),
        "visa_type": "voa",
        "entry_date": today.isoformat(),
        "checked": True,
        **overrides,
    }


async def _setup(client, adults: int = 2, **booking) -> dict:
    workspace = await start_workspace(client)
    room = await make_room_type(client, units=2, max_guests=4)
    plan = await make_rate_plan(client, [room], amount=500000)
    today = property_today(workspace["property"]["timezone"])
    booked = await make_booking(
        client,
        room,
        plan,
        today.isoformat(),
        (today + dt.timedelta(days=2)).isoformat(),
        adults=adults,
        **booking,
    )
    return {"workspace": workspace, "room": room, "plan": plan, "today": today, "booking": booked}


def _url(ctx: dict, tail: str = "") -> str:
    return f"/api/bookings/{ctx['booking']['id']}/guests{tail}"


async def _scan(client, ctx, doc_type: str = "ktp", content: bytes = PHOTO):
    return await client.post(
        _url(ctx, "/scan"),
        files={"file": ("ktp.jpg", content, "image/jpeg")},
        data={"doc_type": doc_type},
    )


async def _room_given(session, client, ctx) -> None:
    line = (
        await session.execute(
            text("SELECT id FROM reservationunit WHERE reservation_id = :b"),
            {"b": ctx["booking"]["id"]},
        )
    ).scalar_one()
    unit = ctx["room"]["units"][0]["id"]
    answer = await client.put(f"{DESK}/lines/{line}/room", json={"unit_id": unit})
    assert answer.status_code == 200, answer.text


def _tenant(ctx: dict) -> dict:
    return {"t": ctx["workspace"]["tenant"]["id"]}


def _code(response) -> str:
    return response.json()["detail"]["code"]


async def _main(client, ctx) -> dict:
    response = await client.get(_url(ctx))
    assert response.status_code == 200, response.text
    return response.json()


# ---- reading ----------------------------------------------------------------------------


async def test_the_booker_is_the_main_guest_without_an_id(pg_client) -> None:
    ctx = await _setup(pg_client)

    body = await _main(pg_client, ctx)

    assert body["main_guest_ready"] is False
    assert body["can_change"] is True
    assert [(g["full_name"], g["is_main"], g["document"]) for g in body["guests"]] == [
        ("Budi Santoso", True, None)
    ]
    assert body["reader"] == {"name": "manual", "simulated": False}


# ---- scanning ---------------------------------------------------------------------------


async def test_without_the_simulator_the_form_starts_empty(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await _scan(pg_client, ctx)

    assert response.status_code == 201, response.text
    assert response.json()["reader"] == {"name": "manual", "simulated": False}
    assert set(response.json()["fields"].values()) == {None}


async def test_the_simulator_suggests_labelled_sample_fields(pg_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ID_READER_SIMULATOR_ENABLED", True)
    ctx = await _setup(pg_client)

    response = await _scan(pg_client, ctx)

    assert response.json()["reader"] == {"name": "simulated", "simulated": True}
    assert response.json()["fields"]["full_name"] == "CONTOH SIMULASI"


async def test_the_photo_is_encrypted_on_disk(pg_client, pg_session, _document_storage) -> None:
    ctx = await _setup(pg_client)

    await _scan(pg_client, ctx)

    files = [path for path in _document_storage.rglob("*") if path.is_file()]
    assert len(files) == 1
    assert PHOTO not in files[0].read_bytes()
    assert not files[0].read_bytes().startswith(b"\xff\xd8\xff")
    kind = await pg_session.execute(
        text(
            "SELECT kind, classification, sha256 FROM document "
            "WHERE kind = 'identity_scan' AND tenant_id = :t"
        ),
        _tenant(ctx),
    )
    assert kind.one() == ("identity_scan", "identity", None)


@pytest.mark.parametrize(
    ("content", "status", "code"),
    [(b"", 422, "image_empty"), (b"<svg onload=alert(1)>", 415, "not_an_image")],
)
async def test_only_real_photos_are_accepted(pg_client, content, status, code) -> None:
    ctx = await _setup(pg_client)

    response = await _scan(pg_client, ctx, content=content)

    assert (response.status_code, _code(response)) == (status, code)


# ---- confirming -------------------------------------------------------------------------


async def test_confirming_a_ktp_encrypts_the_number_and_fills_the_profile(
    pg_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    scan_id = (await _scan(pg_client, ctx)).json()["scan_id"]

    body = await confirm_main_guest_id(pg_client, ctx["booking"]["id"], scan_id=scan_id)

    assert body["main_guest_ready"] is True
    document = body["guests"][0]["document"]
    assert (document["masked_number"], document["has_image"], document["usable"]) == (
        "••••0001",
        True,
        True,
    )
    row = (
        await pg_session.execute(
            text(
                "SELECT doc_number_encrypted, doc_number_hash, verified_by FROM guestdocument "
                "WHERE tenant_id = :t"
            ),
            _tenant(ctx),
        )
    ).one()
    assert KTP_FIELDS["number"].encode() not in bytes(row[0])
    assert KTP_FIELDS["number"] not in row[1]
    assert row[2] is not None
    guest = (
        await pg_session.execute(
            text(
                "SELECT nationality, birth_date::text, gender FROM guest "
                "WHERE full_name = :n AND tenant_id = :t"
            ),
            {"n": "Budi Santoso", **_tenant(ctx)},
        )
    ).one()
    assert tuple(guest) == ("ID", "1990-01-05", "male")


async def test_saving_needs_the_checked_tick(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await pg_client.post(_url(ctx), json={**KTP_FIELDS, "checked": False})

    assert response.status_code == 422


async def test_a_wrong_nik_names_the_problem(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await pg_client.post(_url(ctx), json={**KTP_FIELDS, "birth_date": "1990-01-06"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "id_invalid"
    assert response.json()["detail"]["problems"] == [
        {"code": "nik_birth_date_mismatch", "field": "birth_date"}
    ]


async def test_an_expired_passport_is_refused(pg_client) -> None:
    ctx = await _setup(pg_client)
    past = ctx["today"].replace(year=ctx["today"].year - 1).isoformat()

    response = await pg_client.post(_url(ctx), json=_passport(today=ctx["today"], expires_on=past))

    assert [p["code"] for p in response.json()["detail"]["problems"]] == ["expired"]


async def test_a_photo_serves_one_document_only(pg_client) -> None:
    ctx = await _setup(pg_client)
    scan_id = (await _scan(pg_client, ctx)).json()["scan_id"]
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"], scan_id=scan_id)

    response = await pg_client.post(
        _url(ctx), json={**_passport(today=ctx["today"]), "scan_id": scan_id}
    )

    assert (response.status_code, _code(response)) == (422, "scan_not_usable")


# ---- companions -------------------------------------------------------------------------


async def test_companions_are_added_up_to_the_guest_count_and_can_be_removed(pg_client) -> None:
    ctx = await _setup(pg_client, adults=2)
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"])

    added = await pg_client.post(_url(ctx), json=_passport(today=ctx["today"]))
    third = await pg_client.post(
        _url(ctx), json=_passport(today=ctx["today"], number="PB7654321", full_name="Ben Lee")
    )

    guests = added.json()["guests"]
    assert [(g["full_name"], g["is_main"]) for g in guests] == [
        ("Budi Santoso", True),
        ("Anna Schmidt", False),
    ]
    assert guests[1]["document"]["visa_type"] == "voa"
    assert (third.status_code, _code(third)) == (409, "too_many_guests")
    main_id, companion_id = guests[0]["guest_id"], guests[1]["guest_id"]
    assert _code(await pg_client.delete(_url(ctx, f"/{main_id}"))) == "main_guest_removal"
    assert (await pg_client.delete(_url(ctx, f"/{companion_id}"))).status_code == 204
    assert len((await _main(pg_client, ctx))["guests"]) == 1


async def _doc_rows(session, ctx) -> list:
    rows = await session.execute(
        text(
            "SELECT guest_id, doc_number_last4, doc_number_hash FROM guestdocument "
            "WHERE tenant_id = :t ORDER BY created_at"
        ),
        _tenant(ctx),
    )
    return rows.all()


async def test_correcting_a_number_replaces_it(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"], number="3171230501900002")
    wrong = await _doc_rows(pg_session, ctx)

    body = await confirm_main_guest_id(pg_client, ctx["booking"]["id"])

    rows = await _doc_rows(pg_session, ctx)
    assert len(rows) == 1
    assert rows[0][1] == "0001"
    assert rows[0][2] != wrong[0][2]  # the mistyped number cannot be found again
    assert body["guests"][0]["document"]["masked_number"] == "••••0001"


async def test_another_guest_on_the_booking_cannot_take_the_same_number(pg_client) -> None:
    ctx = await _setup(pg_client)
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"])

    response = await pg_client.post(_url(ctx), json={**KTP_FIELDS, "full_name": "Orang Lain"})

    assert (response.status_code, _code(response)) == (409, "number_on_other_guest")


async def test_a_known_number_never_pulls_in_another_profile_or_photo(
    pg_client, pg_session
) -> None:
    first = await _setup(pg_client)
    scan_id = (await _scan(pg_client, first)).json()["scan_id"]
    await confirm_main_guest_id(pg_client, first["booking"]["id"], scan_id=scan_id)
    later = first["today"] + dt.timedelta(days=5)
    other = await make_booking(
        pg_client,
        first["room"],
        first["plan"],
        later.isoformat(),
        (later + dt.timedelta(days=1)).isoformat(),
        guest_name="Siti",
    )
    ctx = {**first, "booking": other}

    body = (await pg_client.post(_url(ctx), json={**KTP_FIELDS, "full_name": "Siti"})).json()

    companion = body["guests"][1]
    assert companion["full_name"] == "Siti"
    assert companion["document"]["has_image"] is False
    budi = await pg_session.execute(
        text("SELECT count(*) FROM guest WHERE tenant_id = :t AND full_name = 'Budi Santoso'"),
        _tenant(ctx),
    )
    assert budi.scalar_one() == 1  # the first guest's profile is untouched


async def test_a_photo_must_be_one_you_took(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    scan_id = (await _scan(pg_client, ctx)).json()["scan_id"]
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role="manager")
    assert staff

    response = await other_client.post(_url(ctx), json={**KTP_FIELDS, "scan_id": scan_id})

    assert (response.status_code, _code(response)) == (422, "scan_not_usable")


async def test_unconfirmed_photos_are_capped(pg_client, monkeypatch) -> None:
    from app.services import guest_ids

    monkeypatch.setattr(guest_ids, "MAX_UNCONFIRMED_SCANS", 2)
    ctx = await _setup(pg_client)
    for seed in ("a", "b"):
        assert (await _scan(pg_client, ctx, content=image(seed))).status_code == 201

    response = await _scan(pg_client, ctx, content=image("c"))

    assert (response.status_code, _code(response)) == (429, "too_many_scans")


async def test_without_a_booker_the_primary_guest_is_main(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"])
    await pg_client.post(_url(ctx), json=_passport(today=ctx["today"]))
    await pg_session.execute(
        text("UPDATE reservation SET booker_guest_id = NULL WHERE id = :b"),
        {"b": ctx["booking"]["id"]},
    )
    await pg_session.commit()

    body = await _main(pg_client, ctx)

    assert [(g["full_name"], g["is_main"]) for g in body["guests"]] == [
        ("Budi Santoso", True),
        ("Anna Schmidt", False),
    ]
    assert body["main_guest_ready"] is True


async def test_identity_answers_are_never_cached(pg_client) -> None:
    ctx = await _setup(pg_client)

    response = await pg_client.get(_url(ctx))

    assert response.headers["cache-control"] == "no-store"


async def test_a_returning_booker_needs_no_new_scan(pg_client) -> None:
    ctx = await _setup(pg_client, guest_phone="+6281234567890")
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"])
    later = ctx["today"] + dt.timedelta(days=5)
    second = await make_booking(
        pg_client,
        ctx["room"],
        ctx["plan"],
        later.isoformat(),
        (later + dt.timedelta(days=1)).isoformat(),
        guest_phone="+6281234567890",
    )

    body = (await pg_client.get(f"/api/bookings/{second['id']}/guests")).json()

    assert body["main_guest_ready"] is True


# ---- full views -------------------------------------------------------------------------


async def test_revealing_the_number_and_image_is_logged(pg_client) -> None:
    ctx = await _setup(pg_client)
    scan_id = (await _scan(pg_client, ctx)).json()["scan_id"]
    body = await confirm_main_guest_id(pg_client, ctx["booking"]["id"], scan_id=scan_id)
    doc = body["guests"][0]["document"]["id"]

    number = await pg_client.post(_url(ctx, f"/documents/{doc}/reveal"))
    photo = await pg_client.get(_url(ctx, f"/documents/{doc}/image"))
    history = (await pg_client.get(_url(ctx, "/history"))).json()

    assert number.json() == {"number": "3171230501900001"}
    assert number.headers["cache-control"] == "no-store"
    assert (photo.content, photo.headers["content-type"]) == (PHOTO, "image/jpeg")
    assert [entry["event"] for entry in history] == ["image_viewed", "number_viewed", "confirmed"]
    assert all(entry["by"] for entry in history)


async def test_another_booking_s_document_is_not_reachable(pg_client) -> None:
    ctx = await _setup(pg_client)
    body = await confirm_main_guest_id(pg_client, ctx["booking"]["id"])
    doc = body["guests"][0]["document"]["id"]
    other = await make_booking(
        pg_client,
        ctx["room"],
        ctx["plan"],
        ctx["today"].isoformat(),
        (ctx["today"] + dt.timedelta(days=1)).isoformat(),
        guest_name="Siti",
    )

    response = await pg_client.post(f"/api/bookings/{other['id']}/guests/documents/{doc}/reveal")

    assert (response.status_code, _code(response)) == (404, "id_not_found")


# ---- access -----------------------------------------------------------------------------


async def test_without_a_role_nothing_is_reachable(pg_client, other_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)

    assert (await other_client.get(_url(ctx))).status_code == 403
    assert (await _scan(other_client, ctx)).status_code == 403


async def test_view_only_sees_masked_numbers_and_cannot_reveal(
    pg_client, other_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    body = await confirm_main_guest_id(pg_client, ctx["booking"]["id"])
    doc = body["guests"][0]["document"]["id"]
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(pg_session, staff["user_id"], "desk-viewer", ["guestid:view"])

    seen = await other_client.get(_url(ctx))

    assert seen.json()["guests"][0]["document"]["masked_number"] == "••••0001"
    assert "3171230501900001" not in seen.text
    assert (await other_client.post(_url(ctx, f"/documents/{doc}/reveal"))).status_code == 403
    assert (await other_client.get(_url(ctx, f"/documents/{doc}/image"))).status_code == 403
    assert (await other_client.post(_url(ctx), json=KTP_FIELDS)).status_code == 403


async def test_tenants_are_separate(pg_client, other_client) -> None:
    ctx = await _setup(pg_client)
    await start_workspace(other_client)

    assert (await other_client.get(_url(ctx))).status_code == 404
    assert (await other_client.post(_url(ctx), json=KTP_FIELDS)).status_code == 404


async def test_a_cancelled_stay_cannot_change(pg_client) -> None:
    ctx = await _setup(pg_client)
    cancelled = await pg_client.post(
        f"/api/bookings/{ctx['booking']['id']}/cancel", json={"reason": "Batal"}
    )
    assert cancelled.status_code == 200, cancelled.text

    response = await pg_client.post(_url(ctx), json=KTP_FIELDS)

    assert (response.status_code, _code(response)) == (409, "stay_closed")
    assert (await _main(pg_client, ctx))["can_change"] is False


# ---- check-in ---------------------------------------------------------------------------


async def test_check_in_needs_the_main_guest_s_id(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _room_given(pg_session, pg_client, ctx)
    url = f"{DESK}/bookings/{ctx['booking']['id']}/check-in"

    refused = await pg_client.post(url, json={})
    await confirm_main_guest_id(pg_client, ctx["booking"]["id"])
    allowed = await pg_client.post(url, json={})

    assert (refused.status_code, _code(refused)) == (409, "id_missing")
    assert allowed.status_code == 200, allowed.text


async def test_an_expired_passport_does_not_count(pg_client, pg_session) -> None:
    ctx = await _setup(pg_client)
    await _room_given(pg_session, pg_client, ctx)
    await pg_client.post(_url(ctx), json={**_passport(today=ctx["today"]), "guest_id": None})
    await pg_session.execute(
        text("UPDATE guestdocument SET expires_on = DATE '2000-01-01' WHERE tenant_id = :t"),
        _tenant(ctx),
    )
    await pg_session.commit()

    response = await pg_client.post(f"{DESK}/bookings/{ctx['booking']['id']}/check-in", json={})

    assert _code(response) == "id_missing"


async def test_checking_in_without_an_id_needs_a_reason_and_booking_rights(
    pg_client, other_client, pg_session
) -> None:
    ctx = await _setup(pg_client)
    await _room_given(pg_session, pg_client, ctx)
    staff = await add_staff_member(pg_session, other_client, ctx["workspace"], role=None)
    await _give_role(
        pg_session, staff["user_id"], "desk-only", ["frontdesk:view", "frontdesk:edit"]
    )
    url = f"{DESK}/bookings/{ctx['booking']['id']}/check-in"
    body = {"no_id_reason": "Paspor masih di kedutaan"}

    refused = await other_client.post(url, json=body)
    allowed = await pg_client.post(url, json=body)

    assert (refused.status_code, _code(refused)) == (403, "no_id_permission")
    assert allowed.status_code == 200, allowed.text
    logged = await pg_session.execute(
        text(
            "SELECT payload->>'without_id_reason' FROM tenantauditentry "
            "WHERE event_id = 'booking.checked_in' AND entity_id = :b"
        ),
        {"b": ctx["booking"]["id"]},
    )
    assert logged.scalar_one() == "Paspor masih di kedutaan"
