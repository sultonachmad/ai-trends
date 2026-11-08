"""Declarative audit event registry (DS-3 `event_taxonomy[]`).

Define events here; the import-time auto-seed pattern below registers them
into `AUDIT_EVENTS` the moment this module is imported — no separate startup
step required (mirrors how the `rbac` prefab auto-registers permission codes
via `require_permission()` at import time).

Generated projects replace `EVT_USER_LOGIN` below with their own DS-3
`event_taxonomy[]` output. Every event referenced from `audit_service.append()`
must have a matching `AuditEventDef` here — this registry is the single
source of truth for "what can be audited," the same role `backend/docs/rbac-spec.yaml`
plays for permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuditSensitivity(str, Enum):
    """How sensitive the audited action is — informational, not enforced here.

    Generated projects may use this to drive retention windows or alerting;
    this prefab itself does not branch on sensitivity.
    """

    standard = "standard"
    elevated = "elevated"
    critical = "critical"


@dataclass(frozen=True)
class AuditEventDef:
    """One entry in the audit event taxonomy.

    id:              stable event identifier, referenced by
                      `audit_service.append(event_id=...)` and stored verbatim
                      on `AuditEntry.event_id`.
    subject_entity:   the domain entity this event concerns (e.g. "User",
                      "Order") — matches the ds-v2 `event_taxonomy[].subject`.
    origin:           the module/service that raises this event.
    sensitivity:      "standard" | "elevated" | "critical" — see AuditSensitivity.
    description:      human-readable summary, shown in any audit-log viewer.
    """

    id: str
    subject_entity: str
    origin: str
    sensitivity: AuditSensitivity
    description: str


# Auto-seed: every AuditEventDef built via register_event() below is added
# here at import time. audit_service and audit_router both import this module
# to validate that an event_id being appended/queried is a known event.
AUDIT_EVENTS: dict[str, AuditEventDef] = {}


def register_event(event: AuditEventDef) -> AuditEventDef:
    """Register `event` into AUDIT_EVENTS and return it (for `EVT_* = register_event(...)`)."""
    AUDIT_EVENTS[event.id] = event
    return event


# ── Example events — generated projects replace these with their DS-3 output ──

EVT_USER_LOGIN = register_event(
    AuditEventDef(
        id="user-login",
        subject_entity="User",
        origin="authentication_module",
        sensitivity=AuditSensitivity.standard,
        description="User authenticated successfully",
    )
)

EVT_USER_LOGIN_FAILED = register_event(
    AuditEventDef(
        id="user-login-failed",
        subject_entity="User",
        origin="authentication_module",
        sensitivity=AuditSensitivity.elevated,
        description="Authentication attempt failed",
    )
)

EVT_SUBJECT_ERASED = register_event(
    AuditEventDef(
        id="subject-erased",
        subject_entity="User",
        origin="audit_module",
        sensitivity=AuditSensitivity.critical,
        description="A subject's audit entries were anonymised via an erasure request",
    )
)
