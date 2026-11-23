"""Configuration that must never run together.

The simulators let people fabricate guest messages and mark pay links paid. They are
for development. `PREFAB_SESSION_COOKIE_SECURE=true` is the marker of a deployment
served over HTTPS to real users, so the two together stop the app from starting.
"""

from app.config import Settings

DEFAULT_SECRET_KEY = "change-me-in-production"


class UnsafeConfigurationError(RuntimeError):
    """A development-only switch is on in a deployment that looks like production."""


def assert_safe_configuration(settings: Settings) -> None:
    enabled = [
        name
        for name, on in (
            ("PREFAB_MESSAGING_SIMULATOR_ENABLED", settings.MESSAGING_SIMULATOR_ENABLED),
            ("PREFAB_PAYMENT_SIMULATOR_ENABLED", settings.PAYMENT_SIMULATOR_ENABLED),
            ("PREFAB_CHANNEL_SIMULATOR_ENABLED", settings.CHANNEL_SIMULATOR_ENABLED),
        )
        if on
    ]
    if settings.SESSION_COOKIE_SECURE and settings.SECRET_KEY == DEFAULT_SECRET_KEY:
        raise UnsafeConfigurationError(
            "PREFAB_SECRET_KEY must be set when PREFAB_SESSION_COOKIE_SECURE is true."
        )
    if enabled and settings.SESSION_COOKIE_SECURE:
        raise UnsafeConfigurationError(
            f"{' and '.join(enabled)} must be false when PREFAB_SESSION_COOKIE_SECURE is true: "
            "the simulators are for development only."
        )
