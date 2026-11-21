"""US #1653 FR-12a: with rbac, rag-base's real routes follow features:use / features:delete.

Runs on the throwaway Postgres (tests/integration/conftest.py) in an app that has rbac; an app
without rbac skips it. The signed-in user is set with dependency_overrides[get_current_user].
The user and role come from rbac's tests/integration/rbac_users.py, which removes them after
the test. The request is refused before the handler runs, so no vector store or LLM is needed.
"""

from collections.abc import AsyncIterator

import pytest

pytest.importorskip("app.rbac.dependencies")

from app.access import FEATURES_USE
from app.auth.models import User
from app.main import app
from tests.integration.rbac_users import signed_in_as


@pytest.fixture
async def signed_in() -> AsyncIterator[User]:
    async with signed_in_as(app, codes=(FEATURES_USE,)) as user:
        yield user


async def test_a_standard_user_cannot_wipe_the_index(client, signed_in) -> None:
    response = await client.request("DELETE", "/api/rag/collection", json={})

    assert response.status_code == 403, response.text
