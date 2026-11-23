"""Fetching a calendar from a URL an operator pasted — treated as hostile.

Only public HTTPS addresses are reachable. The address is checked when connecting, on
the very IP the socket opens (so DNS cannot answer differently the second time), and
again for every redirect. Time and size are capped. Errors carry a short code only:
never the URL (it is a secret) and never the response body.
"""

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpcore

MAX_URL_LENGTH = 2048
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10.0
HTTPS_PORT = 443
_REDIRECTS = {301, 302, 303, 307, 308}
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIX_TO_FOUR = ipaddress.ip_network("2002::/16")
_IPV4_COMPATIBLE = ipaddress.ip_network("::/96")
_SITE_LOCAL = ipaddress.ip_network("fec0::/10")
_HEADERS = [
    (b"Accept", b"text/calendar, text/plain;q=0.8"),
    (b"Accept-Encoding", b"identity"),
    (b"User-Agent", b"AvailabilityCalendar/1.0"),
]

Resolver = Callable[[str, int], Awaitable[list[str]]]


class IcalFetchError(Exception):
    """A calendar could not be fetched. `code` is safe to store and show."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Fetched:
    status: int
    location: str | None
    body: bytes


Downloader = Callable[[str, Resolver], Awaitable[Fetched]]


def is_public_address(address: str) -> bool:
    """True only for a globally routable unicast address."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public_address(str(ip.ipv4_mapped))
        if any(ip in network for network in (_NAT64, _SIX_TO_FOUR, _IPV4_COMPATIBLE, _SITE_LOCAL)):
            return False
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def check_url(url: str) -> str:
    """The URL if its shape is acceptable (address checks happen when connecting)."""
    if len(url) > MAX_URL_LENGTH or any(ord(char) <= 32 for char in url):
        raise IcalFetchError("invalid_url")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise IcalFetchError("invalid_url") from None
    if parts.scheme.lower() != "https" or not parts.hostname:
        raise IcalFetchError("invalid_url")
    if parts.username or parts.password or port not in (None, HTTPS_PORT):
        raise IcalFetchError("invalid_url")
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        return url
    if not is_public_address(parts.hostname):
        raise IcalFetchError("unsafe_address")
    return url


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        answers = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise IcalFetchError("unreachable") from None
    return [str(answer[4][0]) for answer in answers]


async def public_addresses(host: str, port: int, resolver: Resolver) -> list[str]:
    """Every address of `host`, refused outright if any of them is not public."""
    addresses = await resolver(host, port)
    if not addresses or not all(is_public_address(address) for address in addresses):
        raise IcalFetchError("unsafe_address")
    return addresses


class _PublicOnlyBackend(httpcore.AsyncNetworkBackend):
    """Opens sockets only to addresses it has just checked."""

    def __init__(self, resolver: Resolver) -> None:
        self._resolver = resolver
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable | None = None,
    ) -> httpcore.AsyncNetworkStream:
        failure: Exception | None = None
        for address in await public_addresses(host, port, self._resolver):
            try:
                return await self._inner.connect_tcp(
                    address, port, timeout, local_address, socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                failure = exc
        raise httpcore.ConnectError(str(failure))

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _location(headers: list[tuple[bytes, bytes]]) -> str | None:
    for name, value in headers:
        if name.lower() == b"location":
            return value.decode("latin-1")
    return None


async def _read_capped(response: httpcore.Response) -> bytes:
    received = bytearray()
    async for chunk in response.aiter_stream():
        received.extend(chunk)
        if len(received) > MAX_BYTES:
            raise IcalFetchError("too_large")
    return bytes(received)


async def network_download(url: str, resolver: Resolver) -> Fetched:
    """One GET over a connection pinned to a checked public address."""
    timeouts = dict.fromkeys(("connect", "read", "write", "pool"), TIMEOUT_SECONDS)
    backend = _PublicOnlyBackend(resolver)
    async with httpcore.AsyncConnectionPool(network_backend=backend, retries=0) as pool:
        async with pool.stream(
            "GET", url, headers=_HEADERS, extensions={"timeout": timeouts}
        ) as response:
            location = _location(response.headers)
            body = b"" if response.status != 200 else await _read_capped(response)
            return Fetched(status=response.status, location=location, body=body)


async def _follow(url: str, resolver: Resolver, download: Downloader) -> bytes:
    current = check_url(url)
    for _hop in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        await public_addresses(parts.hostname or "", parts.port or HTTPS_PORT, resolver)
        fetched = await download(current, resolver)
        if fetched.status == 200:
            if len(fetched.body) > MAX_BYTES:
                raise IcalFetchError("too_large")
            return fetched.body
        if fetched.status not in _REDIRECTS or not fetched.location:
            raise IcalFetchError("bad_status")
        current = check_url(urljoin(current, fetched.location))
    raise IcalFetchError("too_many_redirects")


async def fetch_calendar(
    url: str,
    *,
    resolver: Resolver = system_resolver,
    download: Downloader = network_download,
) -> bytes:
    """The calendar at `url`. Raises `IcalFetchError` with a safe code."""
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS * 2):
            return await _follow(url, resolver, download)
    except TimeoutError:
        raise IcalFetchError("timeout") from None
    except httpcore.TimeoutException:
        raise IcalFetchError("timeout") from None
    except (httpcore.NetworkError, httpcore.ProtocolError, httpcore.UnsupportedProtocol):
        raise IcalFetchError("unreachable") from None
    except (ssl.SSLError, OSError):
        raise IcalFetchError("unreachable") from None
