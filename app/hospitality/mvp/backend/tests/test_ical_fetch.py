"""A pasted calendar URL must never reach anything but a public HTTPS address."""

import pytest

from app.channels.ical_fetch import (
    MAX_BYTES,
    Fetched,
    IcalFetchError,
    check_url,
    fetch_calendar,
    is_public_address,
)

PUBLIC = "93.184.216.34"
URL = "https://calendar.example.com/a.ics"


async def public(_host: str, _port: int) -> list[str]:
    return [PUBLIC]


def serving(*responses: Fetched):
    remaining = list(responses)
    seen: list[str] = []

    async def download(url: str, _resolver) -> Fetched:
        seen.append(url)
        return remaining.pop(0)

    download.seen = seen  # type: ignore[attr-defined]
    return download


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::7f00:1",
        "2002:7f00:1::",
        "::7f00:1",
        "::a9fe:a9fe",
        "fec0::1",
        "not-an-ip",
    ],
)
def test_non_public_addresses_are_refused(address: str) -> None:
    assert is_public_address(address) is False


@pytest.mark.parametrize("address", [PUBLIC, "8.8.8.8", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(address: str) -> None:
    assert is_public_address(address) is True


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://example.com/a.ics", "invalid_url"),
        ("ftp://example.com/a.ics", "invalid_url"),
        ("file:///etc/passwd", "invalid_url"),
        ("https://user:pw@example.com/a.ics", "invalid_url"),
        ("https://example.com:8443/a.ics", "invalid_url"),
        ("https://exa mple.com/a.ics", "invalid_url"),
        ("https://example.com:notaport/", "invalid_url"),
        ("https://" + "a" * 2100 + ".com/", "invalid_url"),
        ("https://127.0.0.1/a.ics", "unsafe_address"),
        ("https://[::1]/a.ics", "unsafe_address"),
    ],
)
def test_bad_urls_are_refused(url: str, code: str) -> None:
    with pytest.raises(IcalFetchError) as caught:
        check_url(url)
    assert caught.value.code == code


async def test_a_public_calendar_is_returned() -> None:
    body = await fetch_calendar(
        URL, resolver=public, download=serving(Fetched(200, None, b"BEGIN:VCALENDAR"))
    )
    assert body == b"BEGIN:VCALENDAR"


async def test_a_name_resolving_to_a_private_address_is_refused() -> None:
    async def internal(_host: str, _port: int) -> list[str]:
        return [PUBLIC, "10.0.0.5"]

    download = serving(Fetched(200, None, b"x"))
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(URL, resolver=internal, download=download)
    assert caught.value.code == "unsafe_address"
    assert download.seen == []  # type: ignore[attr-defined]


async def test_a_redirect_to_an_internal_address_is_refused() -> None:
    download = serving(Fetched(302, "https://169.254.169.254/latest/meta-data", b""))
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(URL, resolver=public, download=download)
    assert caught.value.code == "unsafe_address"


async def test_a_redirect_to_http_is_refused() -> None:
    download = serving(Fetched(301, "http://calendar.example.com/a.ics", b""))
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(URL, resolver=public, download=download)
    assert caught.value.code == "invalid_url"


async def test_a_relative_redirect_is_followed() -> None:
    download = serving(Fetched(302, "/b.ics", b""), Fetched(200, None, b"ok"))
    assert await fetch_calendar(URL, resolver=public, download=download) == b"ok"
    assert download.seen[-1] == "https://calendar.example.com/b.ics"  # type: ignore[attr-defined]


async def test_too_many_redirects_stop() -> None:
    download = serving(*[Fetched(302, "/next.ics", b"")] * 5)
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(URL, resolver=public, download=download)
    assert caught.value.code == "too_many_redirects"


async def test_an_oversize_body_is_refused() -> None:
    download = serving(Fetched(200, None, b"x" * (MAX_BYTES + 1)))
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(URL, resolver=public, download=download)
    assert caught.value.code == "too_large"


async def test_an_error_status_is_a_safe_code() -> None:
    with pytest.raises(IcalFetchError) as caught:
        await fetch_calendar(
            URL, resolver=public, download=serving(Fetched(500, None, b"secret page"))
        )
    assert caught.value.code == "bad_status"
    assert "secret" not in str(caught.value)


def test_the_private_token_is_kept_out_of_access_logs() -> None:
    import logging

    from app.routers.calendar_links import _RedactCalendarTokens

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        "%s %s %s",
        ("1.1.1.1", "GET", "/api/ical/SECRET.ics"),
        None,
    )
    _RedactCalendarTokens().filter(record)
    assert "SECRET" not in record.getMessage()
