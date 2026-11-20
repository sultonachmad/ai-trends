"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchBookings } from "@/lib/bookings-api";
import { useLocale } from "@/lib/locale-store";

interface BookingsCardProps {
  className: string;
  /** Today at the property. */
  today: string;
}

interface Summary {
  arrivals: number;
  atRisk: number;
}

/** Dashboard card: who arrives today and which bookings need attention. */
export function BookingsCard({ className, today }: BookingsCardProps) {
  const { t } = useLocale();
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Arrivals of today are in "staying"; bookings at risk can be in either list.
    Promise.all([fetchBookings("staying"), fetchBookings("upcoming")])
      .then(([staying, upcoming]) => {
        if (cancelled) return;
        const live = [...staying.items, ...upcoming.items];
        setSummary({
          arrivals: staying.items.filter((booking) => booking.arrival === today).length,
          atRisk: live.filter((booking) => booking.overbooking_risk).length,
        });
      })
      .catch(() => {
        if (!cancelled) setSummary({ arrivals: 0, atRisk: 0 }); // the link below still works
      });
    return () => {
      cancelled = true;
    };
  }, [today]);

  return (
    <section className={className} aria-labelledby="bookings-heading">
      <h2 id="bookings-heading" className="text-sm font-medium text-muted-foreground">
        {t("dashboard.bookings")}
      </h2>
      <p className="mt-1 text-sm">
        {summary && summary.arrivals > 0
          ? t("dashboard.arrivalsToday", { count: summary.arrivals })
          : t("dashboard.noArrivals")}
      </p>
      {summary && summary.atRisk > 0 && (
        <p className="text-sm font-medium text-destructive">
          {t("dashboard.bookingsAtRisk", { count: summary.atRisk })}
        </p>
      )}
      <Link
        href="/bookings"
        className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
      >
        {t("dashboard.openBookings")}
      </Link>
    </section>
  );
}
