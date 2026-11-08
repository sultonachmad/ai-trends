"""Tenant database models (one sub-package per domain, A-T)."""

from app.models.tenant import (
    ai,
    ancillary,
    billing,
    compliance,
    crm,
    distribution,
    finance_config,
    front_desk,
    guests,
    inventory,
    long_stay,
    operations,
    organisation,
    owners,
    payments,
    plumbing,
    rates,
    reservations,
    revenue,
    staff,
)
from app.models.tenant.ai import *  # noqa: F403
from app.models.tenant.ancillary import *  # noqa: F403
from app.models.tenant.billing import *  # noqa: F403
from app.models.tenant.compliance import *  # noqa: F403
from app.models.tenant.crm import *  # noqa: F403
from app.models.tenant.distribution import *  # noqa: F403
from app.models.tenant.finance_config import *  # noqa: F403
from app.models.tenant.front_desk import *  # noqa: F403
from app.models.tenant.guests import *  # noqa: F403
from app.models.tenant.inventory import *  # noqa: F403
from app.models.tenant.long_stay import *  # noqa: F403
from app.models.tenant.operations import *  # noqa: F403
from app.models.tenant.organisation import *  # noqa: F403
from app.models.tenant.owners import *  # noqa: F403
from app.models.tenant.payments import *  # noqa: F403
from app.models.tenant.plumbing import *  # noqa: F403
from app.models.tenant.rates import *  # noqa: F403
from app.models.tenant.reservations import *  # noqa: F403
from app.models.tenant.revenue import *  # noqa: F403
from app.models.tenant.staff import *  # noqa: F403

__all__ = [
    *organisation.__all__,
    *staff.__all__,
    *inventory.__all__,
    *finance_config.__all__,
    *rates.__all__,
    *guests.__all__,
    *reservations.__all__,
    *billing.__all__,
    *payments.__all__,
    *front_desk.__all__,
    *distribution.__all__,
    *crm.__all__,
    *operations.__all__,
    *owners.__all__,
    *long_stay.__all__,
    *compliance.__all__,
    *ancillary.__all__,
    *revenue.__all__,
    *ai.__all__,
    *plumbing.__all__,
]
