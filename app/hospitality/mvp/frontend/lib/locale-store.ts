"use client";

/**
 * The staff member's chosen UI language, remembered per browser.
 *
 * `useLocale()` re-renders every component using it when the choice changes,
 * including in other tabs. Server render and first paint use the default.
 */

import { useCallback, useSyncExternalStore } from "react";

import { DEFAULT_LOCALE, isLocale, translate, type Locale } from "@/lib/i18n";

const STORAGE_KEY = "ui-locale";
const CHANGE_EVENT = "ui-locale-change";

function readLocale(): Locale {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isLocale(stored) ? stored : DEFAULT_LOCALE;
  } catch {
    // Storage blocked (private mode, policy): fall back without failing the page.
    return DEFAULT_LOCALE;
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useLocale() {
  const locale = useSyncExternalStore(subscribe, readLocale, () => DEFAULT_LOCALE);

  const setLocale = useCallback((next: Locale) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Choice cannot be remembered; it still applies to this page via the event.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale],
  );

  return { locale, setLocale, t };
}
