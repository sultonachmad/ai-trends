"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { useLocale } from "@/lib/locale-store";
import { fetchRoomTypes } from "@/lib/rooms-api";

interface RoomsCardProps {
  className: string;
}

/** Dashboard card: prompts to set up rooms, then links to the calendar. */
export function RoomsCard({ className }: RoomsCardProps) {
  const { t } = useLocale();
  const [inUse, setInUse] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRoomTypes()
      .then((rooms) => {
        if (!cancelled) setInUse(rooms.filter((room) => room.is_active).length);
      })
      .catch(() => {
        if (!cancelled) setInUse(0); // the card still offers the way to the page
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = inUse !== null && inUse > 0;
  return (
    <section className={className} aria-labelledby="rooms-heading">
      <h2 id="rooms-heading" className="text-sm font-medium text-muted-foreground">
        {t("dashboard.rooms")}
      </h2>
      <p className="mt-1 text-sm">
        {ready ? t("dashboard.roomsCount", { count: inUse }) : t("dashboard.roomsEmpty")}
      </p>
      <Link
        href={ready ? "/calendar" : "/rooms"}
        className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
      >
        {ready ? t("dashboard.openCalendar") : t("dashboard.openRooms")}
      </Link>
    </section>
  );
}
