"use client";

/**
 * Sidebar — rbac variant (overwrites auth-session / theme-ttest static versions).
 *
 * Reads nav items from the RBAC context (`useRbac().menuGroups`) so that only
 * routes the current user is permitted to see are shown. The backend already
 * filters the menus array by permission; the frontend renders whatever the
 * server returned — no client-side filtering needed.
 *
 * Grouping: items with children render as a collapsible section (group header
 * + indented child links). Items without children render as a standalone link.
 * A group auto-expands in the sidebar when the current path matches one of its children;
 * in the top bar it is a dropdown that starts closed.
 *
 * Auth state comes from `useSessionState()` (auth-session prefab). The footer
 * shows the signed-in user's email and a logout button.
 *
 * Visual tokens: uses the same CSS custom-property palette as theme-ttest
 * (`--aside-*`, `--primary-color`, etc.) so this file is theme-agnostic.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useSessionState } from "@/components/SessionProvider";
import { PUBLIC_LINKS } from "@/lib/public-links";
import { type MenuGroup, useRbac } from "@/lib/rbac-store";
import NavFrame from "@/components/NavFrame";
import type { NavVariant } from "@/components/NavFrame";

const ICON_MAP: Record<string, string> = {
  // ── Navigation & layout ──
  home: "🏠", // landing page, main page, start
  dashboard: "📊", // overview, analytics summary, KPIs
  menu: "☰", // generic fallback, navigation
  settings: "⚙️", // configuration, preferences, system settings

  // ── People & organisation ──
  users: "👥", // accounts, actors, user list, people, contacts
  user: "👤", // single profile, my account, person detail
  team: "🏢", // department, organisation, company, branch
  candidates: "🧑‍💼", // applicants, job seekers, talent pool
  employees: "🪪", // staff, workforce, personnel
  onboarding: "🚀", // new hire, orientation, welcome

  // ── Hiring / ATS ──
  jobs: "💼", // job descriptions, job postings, vacancies, positions
  offers: "📨", // offer letters, proposals, employment offers
  interviews: "🎙️", // interview schedule, Q&A, screening
  resumes: "📋", // CVs, curriculum vitae, candidate documents
  applications: "📬", // submissions, job applications, apply

  // ── Auth & RBAC ──
  shield: "🛡️", // security, protection, guard
  roles: "🛡️", // role management, access groups
  key: "🔑", // credentials, API keys, secrets
  permissions: "🔐", // access control, authorisation, locks
  lock: "🔒", // restricted, locked, private

  // ── Documents & files ──
  file: "📄", // document, page, single file, report
  files: "📂", // folder, directory, file list, archive
  upload: "📤", // import, attach, send file
  inbox: "📥", // received, download, incoming
  clipboard: "📋", // copy, paste, checklist, form data
  notes: "📝", // memo, remarks, comments, annotations

  // ── Communication ──
  mail: "✉️", // email, messages, notifications, letters
  chat: "💬", // conversation, comments, discussion, support
  bell: "🔔", // alerts, notifications, reminders
  announcement: "📢", // broadcast, news, public notice

  // ── Finance & commerce ──
  money: "💰", // budget, cost, pricing, salary, compensation
  invoice: "🧾", // receipt, billing, payment record
  cart: "🛒", // orders, purchases, shopping
  bank: "🏦", // banking, transactions, finance

  // ── Data & analytics ──
  chart: "📊", // graph, statistics, metrics, reports
  search: "🔍", // find, lookup, query, filter
  database: "🗄️", // storage, data source, records
  calendar: "📅", // schedule, events, dates, timeline, planning
  clock: "🕐", // time tracking, hours, attendance, shifts

  // ── Status & workflow ──
  check: "✅", // approved, completed, done, success
  warning: "⚠️", // alert, attention, risk, issue
  flag: "🚩", // flagged, priority, milestone, review
  star: "⭐", // favourite, rating, featured, bookmarked
  archive: "🗃️", // archived, history, past records

  // ── Domain-specific ──
  medical: "🏥", // clinic, hospital, health, patient
  education: "🎓", // training, courses, learning, certification
  location: "📍", // address, branch, site, geography
  globe: "🌐", // international, language, web, public
  tools: "🔧", // maintenance, utilities, configuration, admin tools
};

function NavIcon({ name }: { name: string | null }) {
  if (!name) return null;
  return (
    <span className="mr-2 text-base leading-none">
      {ICON_MAP[name] ?? "☰"}
    </span>
  );
}

/** Loading placeholder, always a list item of the menu <ul>: short bars in the top bar,
 *  stacked bars in the aside and the mobile panel. */
function NavSkeleton({ variant }: { variant: NavVariant }) {
  if (variant !== "row") {
    return (
      <li data-nav-skeleton={variant} className="space-y-2 py-1" aria-hidden="true">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-lg bg-gray-100" />
        ))}
      </li>
    );
  }
  return (
    <li data-nav-skeleton="row" className="flex items-center gap-2" aria-hidden="true">
      {[...Array(3)].map((_, i) => (
        <span key={i} className="block h-4 w-16 animate-pulse rounded bg-gray-100" />
      ))}
    </li>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
      className={`h-4 w-4 ml-auto transition-transform duration-150 ${open ? "rotate-180" : ""}`}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m19.5 8.25-7.5 7.5-7.5-7.5"
      />
    </svg>
  );
}

/** Collapsible group: header button + indented child links. */
function CollapsibleGroup({
  group,
  pathname,
  onClose,
  row = false,
}: {
  group: MenuGroup;
  pathname: string;
  onClose: () => void;
  row?: boolean;
}) {
  const isChildActive = group.children.some(
    (c) => c.path && (pathname === c.path || pathname.startsWith(c.path + "/")),
  );
  // In the top bar a group is a dropdown: it starts closed, and an outside click or Escape
  // closes it (the rbac Nav.tsx DesktopGroupDropdown precedent). In the aside it auto-expands.
  const [open, setOpen] = useState(!row && isChildActive);
  const ref = useRef<HTMLLIElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!row || !open) return;
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [row, open]);

  return (
    <li ref={ref} className={row ? "relative" : undefined}>
      {/* Group header — toggles collapse, does not navigate */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
        style={{ color: "var(--aside-text-muted)" }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)";
          e.currentTarget.style.color = "var(--aside-text)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = "transparent";
          e.currentTarget.style.color = "var(--aside-text-muted)";
        }}
      >
        <NavIcon name={group.item.icon} />
        <span className="flex-1 text-left">{group.item.name}</span>
        <ChevronIcon open={open} />
      </button>

      {/* Child items */}
      {open && (
        <ul
          className={
            row
              ? "absolute left-0 top-full z-50 mt-2 min-w-[160px] rounded-md border py-1 shadow-lg"
              : "ml-4 mt-0.5 space-y-0.5 border-l pl-3"
          }
          style={
            row
              ? { backgroundColor: "var(--aside-bg)", borderColor: "var(--aside-border)" }
              : { borderColor: "var(--aside-border)" }
          }
        >
          {group.children.map((child) => {
            const active =
              child.path != null &&
              (pathname === child.path ||
                pathname.startsWith(child.path + "/"));
            return (
              <li key={child.id}>
                <Link
                  href={child.path ?? "/"}
                  onClick={() => {
                    if (row) setOpen(false);
                    onClose();
                  }}
                  className="flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                  style={
                    active
                      ? {
                          backgroundColor: "var(--aside-active-bg)",
                          color: "var(--aside-active-text)",
                        }
                      : { color: "var(--aside-text-muted)" }
                  }
                  onMouseEnter={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)";
                      e.currentTarget.style.color = "var(--aside-text)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "var(--aside-text-muted)";
                    }
                  }}
                >
                  <NavIcon name={child.icon} />
                  {child.name}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

/** Standalone link (top-level item with no children). */
function StandaloneLink({
  item,
  pathname,
  onClose,
}: {
  item: MenuGroup["item"];
  pathname: string;
  onClose: () => void;
}) {
  const active =
    item.path != null &&
    (pathname === item.path || pathname.startsWith(item.path + "/"));
  return (
    <li>
      <Link
        href={item.path ?? "/"}
        onClick={onClose}
        className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
        style={
          active
            ? {
                backgroundColor: "var(--aside-active-bg)",
                color: "var(--aside-active-text)",
              }
            : { color: "var(--aside-text-muted)" }
        }
        onMouseEnter={(e) => {
          if (!active) {
            e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)";
            e.currentTarget.style.color = "var(--aside-text)";
          }
        }}
        onMouseLeave={(e) => {
          if (!active) {
            e.currentTarget.style.backgroundColor = "transparent";
            e.currentTarget.style.color = "var(--aside-text-muted)";
          }
        }}
      >
        <NavIcon name={item.icon} />
        {item.name}
      </Link>
    </li>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const {
    isAuthenticated,
    loading: sessionLoading,
    user,
    logout,
  } = useSessionState();
  const { menuGroups, loading: rbacLoading } = useRbac();
  const userEmail = typeof user?.email === "string" ? user.email : undefined;

  const loading = sessionLoading || rbacLoading;

  // BDAI-2058: the login page sits outside the app shell — no sidebar at all.
  if (pathname === "/login" && !isAuthenticated) return null;

  return (
    <NavFrame
      fallback="sidebar"
      menu={(close, variant) => (
        <ul className={variant === "row" ? "flex items-center gap-1" : "space-y-1 px-3 py-4"}>
               <StandaloneLink
                item={{
                  // synthetic Home item: id 0 is the home sentinel — do not gate on truthiness of id (0 is falsy)
                  id: 0,
                  name: "Home",
                  path: "/",
                  icon: "home",
                  order: 0,
                  parent_id: null,
                }}
                pathname={pathname}
                onClose={close}
              />
          {loading ? (
            <NavSkeleton variant={variant} />
          ) : isAuthenticated && menuGroups.length > 0 ? (
            <>
              {menuGroups.map((group) =>
                group.children.length > 0 ? (
                  <CollapsibleGroup
                    key={group.item.id}
                    group={group}
                    pathname={pathname}
                    onClose={close}
                    row={variant === "row"}
                  />
                ) : (
                  <StandaloneLink
                    key={group.item.id}
                    item={group.item}
                    pathname={pathname}
                    onClose={close}
                  />
                ),
              )}
            </>
          ) : !isAuthenticated ? (
            <>
              {PUBLIC_LINKS.map((link, index) => (
                <StandaloneLink
                  key={link.href}
                  item={{
                    // synthetic public item: negative ids never collide with /api/me menu ids
                    id: -(index + 1),
                    name: link.label,
                    path: link.href,
                    icon: null,
                    order: index,
                    parent_id: null,
                  }}
                  pathname={pathname}
                  onClose={close}
                />
              ))}
              <li>
                <Link
                  href="/login"
                  onClick={close}
                  className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium"
                  style={{ color: "var(--aside-text-muted)" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)";
                    e.currentTarget.style.color = "var(--aside-text)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "transparent";
                    e.currentTarget.style.color = "var(--aside-text-muted)";
                  }}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                    className="h-5 w-5"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15M12 9l-3 3m0 0 3 3m-3-3h12.75"
                    />
                  </svg>
                  Login
                </Link>
              </li>
            </>
          ) : null}
        </ul>
      )}
      footer={(close, variant) =>
          // null while rbac loads, so the frame draws no empty footer box.
          variant === "row" && !loading ? (
            <div className="flex items-center gap-2">
              {isAuthenticated ? (
                <>
                  {userEmail && (
                    <span className="max-w-[10rem] truncate text-sm font-medium" style={{ color: "var(--aside-text)" }}>
                      {userEmail}
                    </span>
                  )}
                <button
                  type="button"
                  onClick={() => { close(); logout(); }}
                  className="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
                  style={{ color: "var(--delete-button-text)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                >
                  Logout
                </button>
                </>
              ) : (
                <p className="text-xs" style={{ color: "var(--aside-text-muted)" }}>
                  Built with Ttest
                </p>
              )}
            </div>
          ) : !loading && isAuthenticated ? (
            <div className="space-y-3">
              {userEmail && (
                <div className="px-3">
                  <p
                    className="truncate text-sm font-medium"
                    style={{ color: "var(--aside-text)" }}
                  >
                    {userEmail}
                  </p>
                </div>
              )}
              <button
                type="button"
                onClick={() => {
                  close();
                  logout();
                }}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
                style={{ color: "var(--delete-button-text)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "var(--aside-hover-bg)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--delete-button-text)";
                }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="h-5 w-5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9"
                  />
                </svg>
                Logout
              </button>
            </div>
          ) : !loading ? (
            <p
              className="px-3 text-xs"
              style={{ color: "var(--aside-text-muted)" }}
            >
              Built with Ttest
            </p>
          ) : null
      }
    />
  );
}
