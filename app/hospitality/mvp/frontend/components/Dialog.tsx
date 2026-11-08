"use client";

import { useEffect, useId, useRef } from "react";

/**
 * Shared modal dialog for the Ttest theme.
 *
 * Renders an OPAQUE panel over a dimmed page — the two-layer pattern every
 * dialog in a themed app must follow (see theme AGENTS.md, "Dialog Pattern"):
 *   - overlay: full-viewport scrim (`bg-black/50`) that dims the page
 *   - panel:   opaque surface (`bg-card`) so nothing shows through the content
 *
 * The panel caps its height and scrolls, so tall content never pushes the
 * title or the action buttons off-screen. Focus is moved into the panel on
 * open, trapped while open (Tab/Shift+Tab wrap inside), and returned to the
 * trigger on close. Styling uses the theme's semantic classes only.
 */

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface DialogProps {
  /** Whether the dialog is shown. */
  open: boolean;
  /** Called when the user dismisses (overlay click or Escape). */
  onClose: () => void;
  /** Heading shown at the top of the panel. */
  title?: string;
  /** Panel body (and footer actions). */
  children: React.ReactNode;
}

export function Dialog({ open, onClose, title, children }: DialogProps) {
  // Unique per instance, so two open dialogs never share an id.
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  // Read onClose through a ref so the focus effect can depend on `open` alone.
  // A parent that passes an inline `onClose={() => setOpen(false)}` makes a new
  // function every render; depending on it would re-run the effect on every
  // keystroke — stealing focus out of inputs after one character.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) {
      return;
    }
    const panel = panelRef.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // Move focus into the dialog so keyboard users land inside it.
    panel?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !panel) {
        return;
      }
      // Trap Tab / Shift+Tab within the panel's focusable elements.
      const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusables.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || active === panel) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      // Return focus to whatever opened the dialog.
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? titleId : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Overlay: dims the page behind the dialog */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel: opaque surface — nothing shows through; caps height and scrolls */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className="relative max-h-[calc(100vh-2rem)] w-full max-w-xl overflow-y-auto rounded-xl bg-card text-card-foreground p-6 shadow-lg focus:outline-none"
      >
        {title ? (
          <h2 id={titleId} className="text-lg font-semibold">
            {title}
          </h2>
        ) : null}
        <div className={title ? "mt-4" : undefined}>{children}</div>
      </div>
    </div>
  );
}
