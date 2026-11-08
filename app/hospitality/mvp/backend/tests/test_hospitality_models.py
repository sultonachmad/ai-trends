"""Hospitality models: schema conventions (database-design.md §3) and DTO validation.

Pure metadata/pydantic checks — no database. The DDL itself (RLS, triggers, EXCLUDE)
only exists in PostgreSQL via migrations 0002/0003, which the SQLite test DB never runs.
"""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

import app.models.control_plane as cp
import app.models.tenant as tm
from app.database import startup_tables

AUDIT = {"created_at", "updated_at", "created_by", "updated_by"}


def _entities(module) -> list[type]:
    return [
        getattr(module, n) for n in module.__all__ if not n.endswith(("Create", "Read", "Update"))
    ]


TENANT = _entities(tm)
CONTROL = _entities(cp)
ALL = TENANT + CONTROL


def test_entity_counts_match_design() -> None:
    assert len(CONTROL) == 15
    assert len(TENANT) == 128


@pytest.mark.parametrize("model", ALL, ids=lambda m: m.__name__)
def test_table_name_is_lowercased_class_name(model) -> None:
    assert model.__tablename__ == model.__name__.lower()


def test_hospitality_tables_are_migration_only() -> None:
    startup = {t.name for t in startup_tables()}
    for model in ALL:
        assert model.__table__.info.get("migration_only") is True
        assert model.__tablename__ not in startup


@pytest.mark.parametrize("model", TENANT, ids=lambda m: m.__name__)
def test_tenant_table_isolation_keys(model) -> None:
    table = model.__table__
    assert "tenant_id" in table.c
    assert table.c.tenant_id.nullable is False
    if "id" in table.c:
        uniques = {
            tuple(c.name for c in con.columns)
            for con in table.constraints
            if isinstance(con, UniqueConstraint)
        }
        assert ("tenant_id", "id") in uniques
    for fk in (c for c in table.constraints if isinstance(c, ForeignKeyConstraint)):
        # composite FKs: the DB itself rejects cross-tenant references
        assert fk.column_keys[0] == "tenant_id", fk.name


@pytest.mark.parametrize("model", ALL, ids=lambda m: m.__name__)
def test_dto_conventions(model) -> None:
    create = getattr(cp if model in CONTROL else tm, f"{model.__name__}Create")
    update = getattr(cp if model in CONTROL else tm, f"{model.__name__}Update")
    read = getattr(cp if model in CONTROL else tm, f"{model.__name__}Read")

    assert not AUDIT & set(create.model_fields), "audit fields are server-side"
    assert all(not f.is_required() for f in update.model_fields.values()), "PATCH semantics"
    if model in TENANT:
        assert "tenant_id" not in create.model_fields, "tenant comes from the request context"
    id_col = model.__table__.c.get("id")
    if id_col is not None and id_col.server_default is not None:
        assert "id" not in create.model_fields
        assert read.model_fields["id"].is_required()


@pytest.mark.parametrize(
    ("dto", "secret"),
    [
        (tm.StaffMemberRead, "pin_hash"),
        (tm.GuestDocumentRead, "doc_number_encrypted"),
        (tm.ApiClientRead, "key_hash"),
        (tm.DocumentRead, "storage_key"),
        (tm.PaymentInstrumentRead, "token"),
        (cp.TenantInvitationRead, "token_hash"),
    ],
)
def test_secrets_never_returned(dto, secret) -> None:
    assert secret not in dto.model_fields


def test_tenant_metadata_column_keeps_db_name() -> None:
    assert cp.Tenant.__table__.c.metadata.key == "metadata"
    assert "metadata_" in cp.TenantCreate.model_fields


def test_create_dto_applies_design_defaults() -> None:
    prop = tm.PropertyCreate(
        legal_entity_id=uuid4(), code="UBD", name="Ubud", property_type="villa_portfolio"
    )
    assert prop.currency == "IDR"
    assert prop.timezone == "Asia/Jakarta"
    assert prop.check_in_time == dt.time(14, 0)
    assert prop.amenities == []


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(
            lambda: tm.PropertyCreate(
                legal_entity_id=uuid4(), code="x", name="x", property_type="castle"
            ),
            id="enum-check",
        ),
        pytest.param(lambda: tm.LegalEntityCreate(name="x", currency="RUPIAH"), id="char3"),
        pytest.param(lambda: tm.GuestCreate(full_name="x", vip_level=10), id="range-check"),
        pytest.param(
            lambda: tm.PaymentAllocationCreate(
                payment_id=uuid4(), invoice_id=uuid4(), amount=Decimal("1.234")
            ),
            id="numeric-scale",
        ),
        pytest.param(
            lambda: tm.PaymentAllocationCreate(
                payment_id=uuid4(), invoice_id=uuid4(), amount=Decimal("0")
            ),
            id="amount-gt-0",
        ),
        pytest.param(lambda: tm.UnitTypeUpdate(turnaround_minutes=-5), id="update-keeps-bounds"),
    ],
)
def test_dto_rejects_values_the_db_would_reject(build) -> None:
    """Each case differs from a valid payload (see test below) in one field only."""
    with pytest.raises(ValidationError):
        build()


def test_valid_payloads_pass_the_same_validators() -> None:
    tm.PropertyCreate(legal_entity_id=uuid4(), code="x", name="x", property_type="hotel")
    tm.LegalEntityCreate(name="x", currency="USD")
    tm.GuestCreate(full_name="x", vip_level=9)
    tm.PaymentAllocationCreate(payment_id=uuid4(), invoice_id=uuid4(), amount=Decimal("1.23"))
    tm.UnitTypeUpdate(turnaround_minutes=5)
