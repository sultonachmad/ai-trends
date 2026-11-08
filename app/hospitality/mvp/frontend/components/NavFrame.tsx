"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { screenStyle, type NavPosition } from "@/lib/screen-style";

export type NavVariant = "aside" | "row" | "panel";

export interface NavFrameProps {
  /** The position this menu had before the screen style: a Sidebar passes "sidebar", a Nav "topnav". */
  fallback: NavPosition;
  /** The menu list; `close` shuts the mobile panel after a click. */
  menu: (close: () => void, variant: NavVariant) => React.ReactNode;
  /** Auth block or "Built with Ttest"; the frame places it. A function learns where it is drawn
   * ("aside" stacked, "row" in the top bar, "panel" in the opened mobile panel). */
  footer?: React.ReactNode | ((close: () => void, variant: NavVariant) => React.ReactNode);
}

// Frame colours: the theme's own variable first, then the screen style's, then today's value.
const ASIDE_BG = "var(--aside-bg, var(--sd-aside-bg, #1e1b4b))";
const ASIDE_BORDER = "var(--aside-border, var(--sd-aside-line, #312e81))";
const ASIDE_TEXT = "var(--aside-text, var(--sd-aside-text, #e0e7ff))";
const ASIDE_MUTED = "var(--aside-text-muted, var(--sd-aside-muted, #a5b4fc))";
const ASIDE_HOVER = "var(--aside-hover-bg, var(--sd-aside-hover, var(--sd-aside-line, #312e81)))";
const ASIDE_ACTIVE_BG = "var(--aside-active-bg, var(--sd-aside-active, #312e81))";
const ASIDE_ACTIVE_TEXT = "var(--aside-active-text, var(--sd-aside-active-text, var(--sd-aside-muted, #a5b4fc)))";
const PRIMARY = "var(--primary-color, var(--sd-primary, #6366f1))";

// Top-bar colours of a menu not on the aside palette: the screen style's, then the theme's own
// --nav-bar-* (each globals.css sets them in its colour format), then today's light values.
const BAR_BG = "var(--sd-surface, var(--nav-bar-bg, #ffffff))";
const BAR_LINE = "var(--sd-line, var(--nav-bar-line, #e4e4e7))";
const BAR_TEXT = "var(--sd-text, var(--nav-bar-text, #09090b))";

/** Inline style of one menu item drawn on the aside palette (for menus that are not themed). */
export function asideItemStyle(active: boolean): React.CSSProperties {
  return active
    ? { backgroundColor: ASIDE_ACTIVE_BG, color: ASIDE_ACTIVE_TEXT }
    : { color: ASIDE_MUTED };
}

/** Hover colour shared by the aside-palette items. */
export const ASIDE_HOVER_BG = ASIDE_HOVER;

// Public files do not follow the router's basePath, so the logo src carries it explicitly.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function BrandMark() {
  // `none` shows no mark, as the Screen Design slot does; Auto (null) keeps the shipped "S".
  if (screenStyle.logo === "none") return null;
  if (screenStyle.logo === "image" && screenStyle.logo_path) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={`${BASE_PATH}${screenStyle.logo_path}`}
        alt=""
        className="h-8 w-8 rounded-lg object-contain"
      />
    );
  }
  const text =
    screenStyle.logo === "monogram" && screenStyle.monogram ? screenStyle.monogram : "S";
  return (
    <div
      aria-hidden="true"
      className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold"
      style={{ backgroundColor: PRIMARY, color: "#ffffff" }}
    >
      {text}
    </div>
  );
}

function ToggleIcon({ open, size = "h-5 w-5" }: { open: boolean; size?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      className={size}
    >
      {open ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
      ) : (
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5"
        />
      )}
    </svg>
  );
}

/** True from md up (the aside is always visible there); assumed true until mounted. */
function useIsDesktop(): boolean {
  const [desktop, setDesktop] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const on = () => setDesktop(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return desktop;
}

export default function NavFrame({ fallback, menu, footer }: NavFrameProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const isDesktop = useIsDesktop();
  const asideId = useId();
  const panelId = useId();
  const toggleRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  const position: NavPosition = screenStyle.navigation ?? fallback;
  const name =
    screenStyle.app_name ??
    process.env.NEXT_PUBLIC_APP_NAME ??
    (fallback === "sidebar" ? "Ttest" : "Ttest App");
  const isFn = typeof footer === "function";
  const asideFooter = isFn ? footer(close, "aside") : footer;
  const rowFooter = isFn ? footer(close, "row") : footer;
  const panelFooter = isFn ? footer(close, "panel") : footer;

  if (position === "sidebar") {
    return (
      <>
        {/* Mobile toggle */}
        <button
          ref={toggleRef}
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle sidebar"
          aria-expanded={open}
          aria-controls={asideId}
          className="fixed left-4 top-4 z-50 flex h-10 w-10 items-center justify-center rounded-lg border md:hidden"
          style={{
            color: "var(--secondary-color, var(--sd-muted, #64748b))",
            backgroundColor: "var(--input-bg, var(--sd-surface, #ffffff))",
            borderColor: "var(--input-border, var(--sd-line, #c7d2fe))",
          }}
        >
          <ToggleIcon open={open} />
        </button>

        {/* Mobile backdrop */}
        {open && (
          <div aria-hidden="true" className="fixed inset-0 z-30 bg-black/50 md:hidden" onClick={close} />
        )}

        <aside
          id={asideId}
          inert={!open && !isDesktop}
          data-nav-frame="sidebar"
          className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col transition-transform duration-200 md:translate-x-0 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
          style={{ backgroundColor: ASIDE_BG, borderRight: `1px solid ${ASIDE_BORDER}` }}
        >
          {/* Brand */}
          <div
            className="flex h-16 items-center gap-3 px-6"
            style={{ borderBottom: `1px solid ${ASIDE_BORDER}` }}
          >
            <Link
              href="/"
              aria-current={pathname === "/" ? "page" : undefined}
              onClick={close}
              className="flex items-center gap-3 text-lg font-semibold"
              style={{ color: ASIDE_TEXT }}
            >
              <BrandMark />
              {name}
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto">{menu(close, "aside")}</nav>

          {asideFooter != null && (
            <div
              className="px-3 pb-4"
              style={{ borderTop: `1px solid ${ASIDE_BORDER}`, paddingTop: "1rem" }}
            >
              {asideFooter}
            </div>
          )}
        </aside>
      </>
    );
  }

  // "topnav" and "minimal" draw a top bar. A Sidebar menu keeps the aside palette (the theme's
  const onAside = fallback === "sidebar";
  const minimal = position === "minimal";
  const showMark = onAside || screenStyle.navigation !== null;
  const barClass = onAside ? "" : "border-b";
  const barStyle: React.CSSProperties = onAside
    ? { backgroundColor: ASIDE_BG, borderBottom: `1px solid ${ASIDE_BORDER}` }
    : { backgroundColor: BAR_BG, borderBottomColor: BAR_LINE };

  // "minimal" is the same bar with the menu button at every width (data-nav-minimal).
  return (
    <nav
      data-nav-frame="topnav"
      data-nav-minimal={minimal ? "true" : undefined}
      className={barClass}
      style={barStyle}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link
          href="/"
          aria-current={pathname === "/" ? "page" : undefined}
          className="flex items-center gap-3 text-lg font-semibold"
          style={{ color: onAside ? ASIDE_TEXT : BAR_TEXT }}
        >
          {showMark && <BrandMark />}
          {name}
        </Link>

        {!minimal && (
          <div className="hidden items-center gap-6 sm:flex">
            {menu(close, "row")}
            {rowFooter}
          </div>
        )}

        <div className="flex items-center gap-3">
          {minimal && rowFooter}
          <button
            ref={toggleRef}
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-label="Toggle menu"
            aria-expanded={open}
            aria-controls={panelId}
            className={`flex h-9 w-9 items-center justify-center rounded-md ${
              minimal ? "" : "sm:hidden"
            } ${onAside ? "" : "text-muted-foreground hover:bg-accent"}`}
            style={onAside ? { color: ASIDE_MUTED } : undefined}
          >
            <ToggleIcon open={open} size={onAside ? "h-5 w-5" : "h-6 w-6"} />
          </button>
        </div>
      </div>

      <div
        id={panelId}
        hidden={!open}
        className={`border-t px-6 py-3 ${minimal ? "" : "sm:hidden"}`}
        style={{ borderColor: onAside ? ASIDE_BORDER : BAR_LINE }}
      >
        {menu(close, "panel")}
        {!minimal && panelFooter}
      </div>
    </nav>
  );
}
