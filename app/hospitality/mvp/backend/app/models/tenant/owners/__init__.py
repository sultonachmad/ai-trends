"""Tenant database — N. Owners."""

from app.models.tenant.owners.management_agreement import (
    ManagementAgreement,
    ManagementAgreementCreate,
    ManagementAgreementRead,
    ManagementAgreementUpdate,
)
from app.models.tenant.owners.owner import Owner, OwnerCreate, OwnerRead, OwnerUpdate
from app.models.tenant.owners.owner_payout import (
    OwnerPayout,
    OwnerPayoutCreate,
    OwnerPayoutRead,
    OwnerPayoutUpdate,
)
from app.models.tenant.owners.owner_statement import (
    OwnerStatement,
    OwnerStatementCreate,
    OwnerStatementRead,
    OwnerStatementUpdate,
)
from app.models.tenant.owners.owner_statement_line import (
    OwnerStatementLine,
    OwnerStatementLineCreate,
    OwnerStatementLineRead,
    OwnerStatementLineUpdate,
)
from app.models.tenant.owners.unit_block import (
    UnitBlock,
    UnitBlockCreate,
    UnitBlockRead,
    UnitBlockUpdate,
)
from app.models.tenant.owners.unit_ownership import (
    UnitOwnership,
    UnitOwnershipCreate,
    UnitOwnershipRead,
    UnitOwnershipUpdate,
)

__all__ = [
    "Owner",
    "OwnerCreate",
    "OwnerRead",
    "OwnerUpdate",
    "UnitOwnership",
    "UnitOwnershipCreate",
    "UnitOwnershipRead",
    "UnitOwnershipUpdate",
    "ManagementAgreement",
    "ManagementAgreementCreate",
    "ManagementAgreementRead",
    "ManagementAgreementUpdate",
    "UnitBlock",
    "UnitBlockCreate",
    "UnitBlockRead",
    "UnitBlockUpdate",
    "OwnerStatement",
    "OwnerStatementCreate",
    "OwnerStatementRead",
    "OwnerStatementUpdate",
    "OwnerStatementLine",
    "OwnerStatementLineCreate",
    "OwnerStatementLineRead",
    "OwnerStatementLineUpdate",
    "OwnerPayout",
    "OwnerPayoutCreate",
    "OwnerPayoutRead",
    "OwnerPayoutUpdate",
]
