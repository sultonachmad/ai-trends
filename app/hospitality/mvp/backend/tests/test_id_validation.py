"""Checks on KTP and passport fields before staff can confirm them."""

import datetime as dt

import pytest

from app.services import id_validation as v

TODAY = dt.date(2026, 11, 24)


def _ktp(**overrides) -> v.IdFields:
    values = {
        "doc_type": "ktp",
        "number": "3171230501900001",
        "full_name": "Budi Santoso",
        "birth_date": dt.date(1990, 1, 5),
        "gender": "male",
        "nationality": "ID",
    }
    return v.IdFields(**{**values, **overrides})


def _passport(**overrides) -> v.IdFields:
    values = {
        "doc_type": "passport",
        "number": "PA1234567",
        "full_name": "Anna Schmidt",
        "birth_date": dt.date(1988, 7, 2),
        "gender": "female",
        "nationality": "DE",
        "expires_on": dt.date(2030, 1, 1),
        "visa_type": "voa",
        "entry_date": dt.date(2026, 11, 20),
    }
    return v.IdFields(**{**values, **overrides})


def _codes(fields: v.IdFields) -> list[str]:
    return [problem.code for problem in v.problems(fields, TODAY)]


def test_a_correct_ktp_has_no_problems() -> None:
    assert _codes(_ktp()) == []


def test_a_woman_s_nik_adds_40_to_the_day() -> None:
    assert _codes(_ktp(gender="female")) == ["nik_gender"]
    assert _codes(_ktp(number="3171234501900001", gender="female")) == []


@pytest.mark.parametrize(
    ("number", "code"),
    [
        ("317123050190000", "nik_format"),  # 15 digits
        ("31712305019000012", "nik_format"),  # 17 digits
        ("31712305019O0001", "nik_format"),  # a letter O
        ("0071230501900001", "nik_region"),  # no province 00
        ("3171233202900001", "nik_birth_date"),  # 32 February does not exist
        ("3171230501900000", "nik_serial"),
    ],
)
def test_broken_niks_are_named(number: str, code: str) -> None:
    assert code in _codes(_ktp(number=number))


def test_the_nik_birth_date_must_match_the_card() -> None:
    assert _codes(_ktp(birth_date=dt.date(1990, 1, 6))) == ["nik_birth_date_mismatch"]


def test_nik_spaces_and_dots_are_ignored() -> None:
    assert _codes(_ktp(number="3171 2305 0190 0001")) == []


def test_a_ktp_is_indonesian() -> None:
    assert _codes(_ktp(nationality="MY")) == ["ktp_not_indonesian"]


def test_a_correct_passport_has_no_problems() -> None:
    assert _codes(_passport()) == []


def test_an_expired_passport_is_refused() -> None:
    assert _codes(_passport(expires_on=dt.date(2026, 11, 23))) == ["expired"]


def test_a_passport_needs_an_expiry_date() -> None:
    assert _codes(_passport(expires_on=None)) == ["expiry_missing"]


@pytest.mark.parametrize("number", ["12345", "AB 12-34!", "A" * 13])
def test_odd_passport_numbers_are_refused(number: str) -> None:
    assert _codes(_passport(number=number)) == ["passport_format"]


def test_a_foreign_passport_needs_visa_type_and_entry_date() -> None:
    assert _codes(_passport(visa_type=None, entry_date=None)) == [
        "visa_missing",
        "entry_missing",
    ]


def test_an_indonesian_passport_needs_no_visa() -> None:
    assert _codes(_passport(nationality="ID", visa_type=None, entry_date=None)) == []


def test_unknown_visa_types_and_nationalities_are_refused() -> None:
    assert _codes(_passport(visa_type="tourist")) == ["visa_type"]
    assert _codes(_passport(nationality="XX1")) == ["nationality"]


def test_dates_cannot_be_in_the_future() -> None:
    assert _codes(_passport(birth_date=dt.date(2027, 1, 1))) == ["birth_date_future"]
    assert _codes(_passport(entry_date=dt.date(2026, 12, 1))) == ["entry_future"]


def test_the_name_is_required() -> None:
    assert _codes(_passport(full_name="  ")) == ["name_missing"]


def test_normalised_number_drops_separators() -> None:
    assert _ktp(number="3171 2305.0190-0001").clean_number == "3171230501900001"


def test_a_passport_needs_a_nationality() -> None:
    assert _codes(_passport(nationality=None, visa_type=None, entry_date=None)) == [
        "nationality_missing"
    ]
