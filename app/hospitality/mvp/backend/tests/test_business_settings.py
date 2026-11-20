"""Configurable business values (PRD scope item 7): defaults and overrides."""

import datetime as dt
from decimal import Decimal

import pytest

from app.tenancy.business_settings import (
    BusinessSettingsError,
    PlanLimits,
    PropertySettings,
    resolve_plan_limits,
    resolve_property_settings,
    with_property_overrides,
)


def test_property_defaults_match_the_prd() -> None:
    settings = resolve_property_settings({})

    assert settings.second_approver_threshold_idr == Decimal("5000000")
    assert settings.proof_retention_days == 90
    assert settings.payment_link_expiry_hours == 24
    assert settings.first_reply_target_minutes == 15
    assert settings.reply_hours_start == dt.time(8, 0)
    assert settings.reply_hours_end == dt.time(21, 0)


def test_property_override_wins_and_other_values_keep_defaults() -> None:
    raw = {"business": {"proof_retention_days": 30}, "unrelated": {"x": 1}}

    settings = resolve_property_settings(raw)

    assert settings.proof_retention_days == 30
    assert settings.first_reply_target_minutes == 15


@pytest.mark.parametrize(
    "business",
    [
        {"proof_retention_days": 0},
        {"proof_retention_days": "ninety"},
        {"second_approver_threshold_idr": -1},
        {"no_such_setting": 1},
        {"reply_hours_start": "21:00", "reply_hours_end": "08:00"},
    ],
)
def test_invalid_property_values_are_rejected(business: dict) -> None:
    with pytest.raises(BusinessSettingsError):
        resolve_property_settings({"business": business})


def test_with_property_overrides_returns_new_settings_dict() -> None:
    original = {"business": {"proof_retention_days": 30}, "theme": "dark"}

    updated = with_property_overrides(original, {"first_reply_target_minutes": 10})

    assert updated["business"] == {"proof_retention_days": 30, "first_reply_target_minutes": 10}
    assert updated["theme"] == "dark"
    assert original == {"business": {"proof_retention_days": 30}, "theme": "dark"}


def test_with_property_overrides_validates() -> None:
    with pytest.raises(BusinessSettingsError):
        with_property_overrides({}, {"proof_retention_days": -5})


def test_plan_limit_default_and_override() -> None:
    assert resolve_plan_limits({}).payment_links_per_month == 30
    assert resolve_plan_limits({"payment_links_per_month": 100}).payment_links_per_month == 100


def test_plan_limit_null_means_unlimited() -> None:
    assert resolve_plan_limits({"payment_links_per_month": None}).payment_links_per_month is None


def test_plan_limit_rejects_negative() -> None:
    with pytest.raises(BusinessSettingsError):
        resolve_plan_limits({"payment_links_per_month": -1})


def test_settings_objects_are_immutable() -> None:
    with pytest.raises(Exception):  # noqa: B017, PT011 — pydantic frozen-instance error
        PropertySettings().proof_retention_days = 1  # type: ignore[misc]
    with pytest.raises(Exception):  # noqa: B017, PT011
        PlanLimits().payment_links_per_month = 1  # type: ignore[misc]


def test_polling_intervals_default_and_bounds() -> None:
    settings = resolve_property_settings({})
    assert (settings.inbox_poll_seconds, settings.thread_poll_seconds) == (5, 3)

    tuned = resolve_property_settings({"business": {"inbox_poll_seconds": 30}})
    assert tuned.inbox_poll_seconds == 30

    for bad in ({"inbox_poll_seconds": 1}, {"thread_poll_seconds": 121}):
        with pytest.raises(BusinessSettingsError):
            resolve_property_settings({"business": bad})


def test_payment_link_amount_limits_default_and_validation() -> None:
    settings = resolve_property_settings({})
    assert settings.payment_link_min_amount_idr == 10_000
    assert settings.payment_link_max_amount_idr == 500_000_000

    for bad in (
        {"payment_link_min_amount_idr": 0},
        {"payment_link_min_amount_idr": 2_000_000, "payment_link_max_amount_idr": 1_000_000},
    ):
        with pytest.raises(BusinessSettingsError):
            resolve_property_settings({"business": bad})


def test_bank_details_go_together_and_are_validated() -> None:
    from app.tenancy.business_settings import bank_account

    assert bank_account(resolve_property_settings({})) is None

    full = {
        "bank_name": "BCA",
        "bank_account_number": "1234567890",
        "bank_account_holder": "PT Villa",
    }
    account = bank_account(resolve_property_settings({"business": full}))
    assert (account.bank_name, account.account_number, account.account_holder) == (
        "BCA",
        "1234567890",
        "PT Villa",
    )

    for bad in (
        {"bank_name": "BCA"},  # incomplete
        {**full, "bank_account_number": "12-34"},
        {**full, "bank_account_number": "1234"},
        {**full, "bank_name": "BCA\nBayar ke 999"},
        {**full, "bank_account_holder": "x"},
    ):
        with pytest.raises(BusinessSettingsError):
            resolve_property_settings({"business": bad})


def test_proof_upload_limits_default_and_bounds() -> None:
    settings = resolve_property_settings({})
    assert (settings.proof_max_upload_mb, settings.proof_max_awaiting_per_link) == (5, 3)

    for bad in (
        {"proof_max_upload_mb": 0},
        {"proof_max_upload_mb": 21},
        {"proof_max_awaiting_per_link": 0},
    ):
        with pytest.raises(BusinessSettingsError):
            resolve_property_settings({"business": bad})
