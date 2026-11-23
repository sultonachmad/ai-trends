"""Development-only switches cannot be on in a production-like deployment."""

import pytest

from app.config import Settings
from app.security.startup_checks import UnsafeConfigurationError, assert_safe_configuration


def _settings(**overrides) -> Settings:
    values = {
        "MESSAGING_SIMULATOR_ENABLED": False,
        "PAYMENT_SIMULATOR_ENABLED": False,
        "CHANNEL_SIMULATOR_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "SECRET_KEY": "a-real-secret-for-tests",
    }
    return Settings(**{**values, **overrides})


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"SESSION_COOKIE_SECURE": True},
        {"MESSAGING_SIMULATOR_ENABLED": True, "PAYMENT_SIMULATOR_ENABLED": True},
    ],
)
def test_safe_combinations_start(overrides) -> None:
    assert_safe_configuration(_settings(**overrides))


@pytest.mark.parametrize(
    ("switch", "name"),
    [
        ("MESSAGING_SIMULATOR_ENABLED", "PREFAB_MESSAGING_SIMULATOR_ENABLED"),
        ("PAYMENT_SIMULATOR_ENABLED", "PREFAB_PAYMENT_SIMULATOR_ENABLED"),
        ("CHANNEL_SIMULATOR_ENABLED", "PREFAB_CHANNEL_SIMULATOR_ENABLED"),
    ],
)
def test_a_simulator_with_secure_cookies_refuses_to_start(switch, name) -> None:
    with pytest.raises(UnsafeConfigurationError) as error:
        assert_safe_configuration(_settings(SESSION_COOKIE_SECURE=True, **{switch: True}))

    assert name in str(error.value)


def test_the_default_secret_refuses_to_start_with_secure_cookies() -> None:
    with pytest.raises(UnsafeConfigurationError):
        assert_safe_configuration(
            _settings(SESSION_COOKIE_SECURE=True, SECRET_KEY="change-me-in-production")
        )
