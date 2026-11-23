"""The channel report: production by booking source for a period."""

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class ReportFigures(BaseModel):
    bookings: int  # confirmed bookings with a night in the period
    nights: int  # room nights in the period
    revenue: Decimal
    average_per_night: Decimal
    cancelled: int
    cancellation_rate: Decimal  # percent, one decimal
    commission: Decimal
    net_revenue: Decimal


class ReportRow(ReportFigures):
    code: str
    name: str
    is_direct: bool
    revenue_share: Decimal  # percent of total revenue, one decimal


class ChannelReport(BaseModel):
    start: dt.date
    end: dt.date
    rows: list[ReportRow]
    direct: ReportFigures
    channels: ReportFigures
    total: ReportFigures
