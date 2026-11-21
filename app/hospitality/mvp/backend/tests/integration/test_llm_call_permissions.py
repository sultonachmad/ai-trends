"""US #1653 FR-12a: with rbac, a user with no role cannot call llm-call's chat route.

Runs on the throwaway Postgres (tests/integration/conftest.py) in an app that has rbac; an app
without rbac skips it. The signed-in user is set with dependency_overrides[get_current_user].
The user and role come from rbac's tests/integration/rbac_users.py, which removes them after
the test. The request is refused before the handler runs, so no vector store or LLM is needed.
"""

from collections.abc import AsyncIterator

import pytest

pytest.importorskip("app.rbac.dependencies")

from app.auth.models import User
from app.main import app
from tests.integration.rbac_users import signed_in_as


@pytest.fixture
async def signed_in() -> AsyncIterator[User]:
    async with signed_in_as(app) as user:
        yield user


async def test_a_user_with_no_role_cannot_chat(client, signed_in) -> None:
    response = await client.post("/api/llm/chat", json={"messages": []})

    assert response.status_code == 403, response.text
