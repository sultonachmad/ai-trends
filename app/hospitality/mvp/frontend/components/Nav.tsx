"use client";

/**
 * Nav — rbac variant (overwrites auth-session / base static versions).
 *
 * Replaces the static `links` array with permission-filtered menus from
 * `useRbac().menuGroups` (returned by `/api/me`). The backend already filters
 * the list by permission; the frontend renders whatever the server returned.
 *
 * Grouping:
 * - Desktop: standalone items render as plain links; grouped items render as a
 *   button that shows a positioned dropdown panel with the child links.
 * - Mobile: all items render inline; group children are indented below their
 *   parent header (no separate toggle — groups expand naturally in the list).
 *
 * Auth state (login/logout button) comes from `useSessionState()`.
 * Used in apps that prefer a horizontal top-nav layout (no sidebar).
 * When theme-ttest is installed the layout uses Sidebar instead — both
 * components read the same `useRbac()` data.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useSessionState } from "@/components/SessionProvider";
import { PUBLIC_LINKS } from "@/lib/public-links";
import { type MenuGroup, useRbac } from "@/lib/rbac-store";
import NavFrame from "@/components/NavFrame";
import { asideItemStyle } from "@/components/NavFrame";

/** Desktop: dropdown trigger + positioned panel for a grouped menu. */
function DesktopGroupDropdown({
  group,
  pathname,
}: {
  group: MenuGroup;
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const isGroupActive = group.children.some(
    (c) => c.path && (pathname === c.path || pathname.startsWith(c.path + "/")),
  );

  // Close on an outside click, or on Escape (focus goes back to the button).
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1 text-sm font-medium transition-colors ${
          isGroupActive
            ? "text-foreground"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {group.item.name}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className={`h-3.5 w-3.5 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 min-w-[160px] rounded-md border border-border bg-background py-1 shadow-lg">
          {group.children.map((child) => {
            const isActive =
              child.path != null &&
              (pathname === child.path || pathname.startsWith(child.path + "/"));
            return (
              <Link
                key={child.id}
                href={child.path ?? "/"}
                onClick={() => setOpen(false)}
                className={`block px-4 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-accent font-medium text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {child.name}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, loading: sessionLoading, logout } = useSessionState();
  const { menuGroups, loading: rbacLoading } = useRbac();

  const loading = sessionLoading || rbacLoading;

  // BDAI-2058: the login page sits outside the app shell — no nav at all.
  if (pathname === "/login" && !isAuthenticated) return null;

  return (
    <NavFrame
      fallback="topnav"
      menu={(close, variant) => {
        if (variant === "aside") {
          const isActive = (path: string | null) =>
            path != null && (pathname === path || pathname.startsWith(path + "/"));
          return (
            <ul className="space-y-1 px-3 py-4">
              {!loading &&
                menuGroups.map((group) => (
                  <li key={group.item.id}>
                    {group.children.length > 0 ? (
                      <>
                        <span
                          className="block px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide"
                          style={asideItemStyle(false)}
                        >
                          {group.item.name}
                        </span>
                        {group.children.map((child) => (
                          <Link
                            key={child.id}
                            href={child.path ?? "/"}
                            onClick={close}
                            className="flex items-center rounded-lg px-5 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                            style={asideItemStyle(isActive(child.path))}
                          >
                            {child.name}
                          </Link>
                        ))}
                      </>
                    ) : (
                      <Link
                        href={group.item.path ?? "/"}
                        onClick={close}
                        className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                        style={asideItemStyle(isActive(group.item.path))}
                      >
                        {group.item.name}
                      </Link>
                    )}
                  </li>
                ))}
              {(!loading && !isAuthenticated ? PUBLIC_LINKS : []).map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      onClick={close}
                      className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                      style={asideItemStyle(isActive(link.href))}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              {!loading && (
                <li>
                  {isAuthenticated ? (
                    <button
                      type="button"
                      onClick={() => { close(); logout(); }}
                      className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                      style={asideItemStyle(false)}
                    >
                      Logout
                    </button>
                  ) : (
                    <Link
                      href="/login"
                      onClick={close}
                      className="flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:opacity-80"
                      style={asideItemStyle(false)}
                    >
                      Login
                    </Link>
                  )}
                </li>
              )}
            </ul>
          );
        }

        if (variant === "row") {
          return (
            <>
              {!loading &&
                menuGroups.map((group) =>
                  group.children.length > 0 ? (
                    <DesktopGroupDropdown
                      key={group.item.id}
                      group={group}
                      pathname={pathname}
                    />
                  ) : (
                    <Link
                      key={group.item.id}
                      href={group.item.path ?? "/"}
                      className={
                        group.item.path != null &&
                        (pathname === group.item.path ||
                          pathname.startsWith(group.item.path + "/"))
                          ? "text-sm font-medium text-foreground"
                          : "text-sm font-medium text-muted-foreground hover:text-foreground"
                      }
                    >
                      {group.item.name}
                    </Link>
                  ),
                )}

              {!loading &&
                !isAuthenticated &&
                PUBLIC_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={
                      pathname === link.href || pathname.startsWith(link.href + "/")
                        ? "text-sm font-medium text-foreground"
                        : "text-sm font-medium text-muted-foreground hover:text-foreground"
                    }
                  >
                    {link.label}
                  </Link>
                ))}

              {loading && (
                <div className="flex items-center gap-6">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-4 w-16 animate-pulse rounded bg-muted" />
                  ))}
                </div>
              )}

              {/* Auth button */}
              {!loading &&
                (isAuthenticated ? (
                  <button
                    type="button"
                    onClick={() => logout()}
                    className="rounded-md bg-secondary px-3 py-1.5 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
                  >
                    Logout
                  </button>
                ) : (
                  <Link
                    href="/login"
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Login
                  </Link>
                ))}
            </>
          );
        }

        return (
          <div className="flex flex-col gap-1">
            {!loading &&
              menuGroups.map((group) => (
                <div key={group.item.id}>
                  {group.children.length > 0 ? (
                    <>
                      {/* Group label (non-clickable) */}
                      <span className="block px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {group.item.name}
                      </span>
                      {/* Indented children */}
                      {group.children.map((child) => {
                        const isActive =
                          child.path != null &&
                          (pathname === child.path ||
                            pathname.startsWith(child.path + "/"));
                        return (
                          <Link
                            key={child.id}
                            href={child.path ?? "/"}
                            onClick={close}
                            className={
                              isActive
                                ? "block rounded-md px-5 py-2 text-sm font-medium text-foreground"
                                : "block rounded-md px-5 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
                            }
                          >
                            {child.name}
                          </Link>
                        );
                      })}
                    </>
                  ) : (
                    <Link
                      href={group.item.path ?? "/"}
                      onClick={close}
                      className={
                        group.item.path != null &&
                        (pathname === group.item.path ||
                          pathname.startsWith(group.item.path + "/"))
                          ? "block rounded-md px-3 py-2 text-sm font-medium text-foreground"
                          : "block rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
                      }
                    >
                      {group.item.name}
                    </Link>
                  )}
                </div>
              ))}

            {!loading &&
              !isAuthenticated &&
              PUBLIC_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={close}
                  className={
                    pathname === link.href || pathname.startsWith(link.href + "/")
                      ? "block rounded-md px-3 py-2 text-sm font-medium text-foreground"
                      : "block rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground"
                  }
                >
                  {link.label}
                </Link>
              ))}

            {!loading &&
              (isAuthenticated ? (
                <button
                  type="button"
                  onClick={() => {
                    close();
                    logout();
                  }}
                  className="rounded-md px-3 py-2 text-left text-sm font-medium text-destructive hover:bg-destructive/10"
                >
                  Logout
                </button>
              ) : (
                <Link
                  href="/login"
                  onClick={close}
                  className="rounded-md px-3 py-2 text-left text-sm font-medium text-primary hover:bg-primary/10"
                >
                  Login
                </Link>
              ))}
          </div>
        );
      }}
    />
  );
}
