"""Tenant database — R. Revenue management."""

from app.models.tenant.revenue.budget import Budget, BudgetCreate, BudgetRead, BudgetUpdate
from app.models.tenant.revenue.competitor import (
    Competitor,
    CompetitorCreate,
    CompetitorRead,
    CompetitorUpdate,
)
from app.models.tenant.revenue.competitor_rate import (
    CompetitorRate,
    CompetitorRateCreate,
    CompetitorRateRead,
    CompetitorRateUpdate,
)
from app.models.tenant.revenue.demand_event import (
    DemandEvent,
    DemandEventCreate,
    DemandEventRead,
    DemandEventUpdate,
)
from app.models.tenant.revenue.forecast_day import (
    ForecastDay,
    ForecastDayCreate,
    ForecastDayRead,
    ForecastDayUpdate,
)
from app.models.tenant.revenue.price_recommendation import (
    PriceRecommendation,
    PriceRecommendationCreate,
    PriceRecommendationRead,
    PriceRecommendationUpdate,
)

__all__ = [
    "DemandEvent",
    "DemandEventCreate",
    "DemandEventRead",
    "DemandEventUpdate",
    "Competitor",
    "CompetitorCreate",
    "CompetitorRead",
    "CompetitorUpdate",
    "CompetitorRate",
    "CompetitorRateCreate",
    "CompetitorRateRead",
    "CompetitorRateUpdate",
    "ForecastDay",
    "ForecastDayCreate",
    "ForecastDayRead",
    "ForecastDayUpdate",
    "PriceRecommendation",
    "PriceRecommendationCreate",
    "PriceRecommendationRead",
    "PriceRecommendationUpdate",
    "Budget",
    "BudgetCreate",
    "BudgetRead",
    "BudgetUpdate",
]
