"use client";

/**
 * DynamicNav — renders navigation links from the server-returned menus array.
 *
 * Menus are already filtered by the backend (/api/me) so that only items the
 * current user is allowed to see are returned. The frontend does NOT filter
 * menus itself — it renders whatever the server sent.
 *
 * Icons: uses a simple text/emoji map keyed by the `icon` string stored in
 * each menu row. Add entries to `ICON_MAP` below to support more icon names.
 * Replace with a proper icon library (Heroicons, Lucide, etc.) as needed.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRbac } from "@/lib/rbac-store";
import NavFrame from "@/components/NavFrame";
import { asideItemStyle } from "@/components/NavFrame";

const ICON_MAP: Record<string, string> = {
  users: "👥",
  shield: "🛡️",
  key: "🔑",
  home: "🏠",
  settings: "⚙️",
  chart: "📊",
  file: "📄",
  inbox: "📥",
};

function NavIcon({ name }: { name: string | null }) {
  if (!name) return null;
  const icon = ICON_MAP[name] ?? "•";
  return <span className="mr-2 text-base leading-none">{icon}</span>;
}

export function DynamicNav() {
  const { menus, loading } = useRbac();
  const pathname = usePathname();

  return (
    <NavFrame
      fallback="sidebar"
      menu={(close, variant) => (
        <ul className={variant === "row" ? "flex items-center gap-1" : "space-y-1 px-3 py-4"}>
          {loading
            ? [...Array(3)].map((_, i) => (
                <li key={i} aria-hidden="true">
                  <div
                    className={`animate-pulse rounded bg-gray-100 ${variant === "row" ? "h-4 w-16" : "h-8"}`}
                  />
                </li>
              ))
            : menus.map((item) => {
                const active =
                  item.path != null &&
                  (pathname === item.path || pathname.startsWith(item.path + "/"));
                return (
                  <li key={item.id}>
                    <Link
                      href={item.path ?? "/"}
                      onClick={close}
                      className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                      style={asideItemStyle(active)}
                    >
                      <NavIcon name={item.icon} />
                      {item.name}
                    </Link>
                  </li>
                );
              })}
        </ul>
      )}
    />
  );
}
