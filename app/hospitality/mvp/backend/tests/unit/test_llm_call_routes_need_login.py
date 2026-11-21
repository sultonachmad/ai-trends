"""US #1653 FR-11: with a login prefab installed, every LLM route answers 401 without a session.

No session cookie, so the session middleware never reads its store and get_current_user raises
401 before the route or the database runs (spec-bdai-1653 §6). An app with no login prefab
leaves these routes open on purpose (ADR-0058 Decision 2) and skips this file.
"""

import httpx
import pytest

pytest.importorskip("app.session.dependencies")

from app.main import app

ROUTES = [
    ("POST", "/api/llm/chat"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
async def test_the_route_needs_a_session(method: str, path: str) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path)

    assert response.status_code == 401, response.text
