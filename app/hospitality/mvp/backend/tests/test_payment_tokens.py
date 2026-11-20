"""Payment-link tokens: unguessable, well-formed, stored only as a fingerprint."""

import pytest

from app.payments.tokens import fingerprint, is_well_formed, new_token


def test_tokens_are_long_unique_and_url_safe() -> None:
    tokens = {new_token() for _ in range(200)}

    assert len(tokens) == 200
    assert all(len(token) == 43 for token in tokens)
    assert all(is_well_formed(token) for token in tokens)


def test_fingerprint_is_stable_and_not_the_token() -> None:
    token = new_token()

    assert fingerprint(token) == fingerprint(token)
    assert len(fingerprint(token)) == 64
    assert token not in fingerprint(token)
    assert fingerprint(token) != fingerprint(new_token())


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "short",
        "a" * 42,
        "a" * 44,
        "a" * 42 + "!",
        "../" + "a" * 40,
        "a" * 42 + " ",
        "é" + "a" * 42,
    ],
)
def test_malformed_tokens_are_recognised(bad: str) -> None:
    assert is_well_formed(bad) is False
