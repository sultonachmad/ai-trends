"""Pure helpers of the payment-link service: money text, chat message, states."""

import datetime as dt
from decimal import Decimal

import pytest

from app.config import frontend_base_url, settings
from app.models.tenant import PaymentLink
from app.services.payment_links import (
    chat_message,
    effective_status,
    format_rupiah,
    money,
    pay_url,
    state_for_people,
)

NOW = dt.datetime(2026, 11, 20, 10, 0, tzinfo=dt.UTC)


def _link(**overrides) -> PaymentLink:
    values = {
        "amount": Decimal("500000"),
        "description": "DP Villa",
        "expires_at": NOW + dt.timedelta(hours=24),
        "status": "active",
    }
    return PaymentLink(**{**values, **overrides})


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("850000"), "Rp 850.000"),
        (Decimal("1700000.00"), "Rp 1.700.000"),
        (10000, "Rp 10.000"),
        (Decimal("999"), "Rp 999"),
    ],
)
def test_format_rupiah(amount, text) -> None:
    assert format_rupiah(amount) == text


def test_money_always_has_two_decimals() -> None:
    assert str(money(Decimal("850000"))) == "850000.00"
    assert str(money(Decimal("850000.00"))) == "850000.00"


@pytest.mark.parametrize(
    ("status", "expires_in", "expected", "for_people"),
    [
        ("active", dt.timedelta(seconds=1), "active", "pending"),
        ("active", dt.timedelta(0), "expired", "expired"),
        ("active", dt.timedelta(hours=-1), "expired", "expired"),
        ("paid", dt.timedelta(hours=-1), "paid", "paid"),
        ("cancelled", dt.timedelta(hours=1), "cancelled", "cancelled"),
        ("expired", dt.timedelta(hours=1), "expired", "expired"),
    ],
)
def test_effective_status(status, expires_in, expected, for_people) -> None:
    link = _link(status=status, expires_at=NOW + expires_in)

    assert effective_status(link, NOW) == expected
    assert state_for_people(link, NOW) == for_people


def test_chat_message_for_a_plain_amount_uses_the_property_timezone() -> None:
    text = chat_message(_link(), "https://app.test/pay/abc", "Asia/Makassar")

    assert text.splitlines() == [
        "DP Villa",
        "Jumlah: Rp 500.000",
        "Bayar di sini: https://app.test/pay/abc",
        "Berlaku sampai 21/11/2026 18:00",  # 10:00 UTC + 8h
    ]


def test_chat_message_for_a_down_payment() -> None:
    text = chat_message(
        _link(deposit_of_total=Decimal("1700000")), "https://app.test/pay/abc", "Asia/Jakarta"
    )

    assert "DP Rp 500.000 dari total Rp 1.700.000" in text
    assert "Jumlah:" not in text


def test_chat_message_survives_a_bad_timezone_and_missing_description() -> None:
    text = chat_message(_link(description=None), "https://app.test/pay/abc", "Not/AZone")

    assert text.startswith("Pembayaran\n")
    assert "Berlaku sampai 21/11/2026 10:00" in text


def test_pay_url_uses_the_configured_frontend_address(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://stay.example.com/")
    assert pay_url("tok") == "https://stay.example.com/pay/tok"

    monkeypatch.setattr(settings, "FRONTEND_URL", "")
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["http://localhost:3100", "http://other"])
    assert frontend_base_url() == "http://localhost:3100"
    assert pay_url("tok") == "http://localhost:3100/pay/tok"
