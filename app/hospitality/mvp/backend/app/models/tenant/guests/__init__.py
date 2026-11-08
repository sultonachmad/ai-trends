"""Tenant database — F. Accounts & guests."""

from app.models.tenant.guests.account import Account, AccountCreate, AccountRead, AccountUpdate
from app.models.tenant.guests.guest import Guest, GuestCreate, GuestRead, GuestUpdate
from app.models.tenant.guests.guest_consent import (
    GuestConsent,
    GuestConsentCreate,
    GuestConsentRead,
    GuestConsentUpdate,
)
from app.models.tenant.guests.guest_document import (
    GuestDocument,
    GuestDocumentCreate,
    GuestDocumentRead,
    GuestDocumentUpdate,
)
from app.models.tenant.guests.guest_preference import (
    GuestPreference,
    GuestPreferenceCreate,
    GuestPreferenceRead,
    GuestPreferenceUpdate,
)

__all__ = [
    "Account",
    "AccountCreate",
    "AccountRead",
    "AccountUpdate",
    "Guest",
    "GuestCreate",
    "GuestRead",
    "GuestUpdate",
    "GuestDocument",
    "GuestDocumentCreate",
    "GuestDocumentRead",
    "GuestDocumentUpdate",
    "GuestPreference",
    "GuestPreferenceCreate",
    "GuestPreferenceRead",
    "GuestPreferenceUpdate",
    "GuestConsent",
    "GuestConsentCreate",
    "GuestConsentRead",
    "GuestConsentUpdate",
]
