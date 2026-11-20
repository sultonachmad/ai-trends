"""Response headers for addresses that carry a secret token in the path.

A pay link's token is its credential. Responses for those paths must not be cached,
must not hand the address to other sites as a referrer, and must stay out of search
indexes — on success and on every error alike, hence a middleware.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOKEN_PATH_PREFIXES: tuple[str, ...] = ("/api/pay/", "/api/simulator/payments/")
TOKEN_PATH_HEADERS: dict[str, str] = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


class TokenPathHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(TOKEN_PATH_PREFIXES):
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in TOKEN_PATH_HEADERS.items():
                    headers[name] = value
            await send(message)

        await self._app(scope, receive, send_with_headers)
