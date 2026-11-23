/** Report calls (backend: app/routers/reports.py). */

import { request } from "@/lib/api-client";

export interface ReportFigures {
  bookings: number;
  nights: number;
  revenue: string;
  average_per_night: string;
  cancelled: number;
  cancellation_rate: string;
  commission: string;
  net_revenue: string;
}

export interface ReportRow extends ReportFigures {
  code: string;
  name: string;
  is_direct: boolean;
  revenue_share: string;
}

export interface ChannelReport {
  start: string;
  end: string;
  rows: ReportRow[];
  direct: ReportFigures;
  channels: ReportFigures;
  total: ReportFigures;
}

export const fetchChannelReport = (from: string, to: string) =>
  request<ChannelReport>(
    `/api/reports/channels?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
