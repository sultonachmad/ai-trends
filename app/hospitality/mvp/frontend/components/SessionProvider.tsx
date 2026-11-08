"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { fetchSession, logout as logoutRequest, type SessionUser } from "@/lib/session";

interface SessionState {
  user: SessionUser | null;
  isAuthenticated: boolean;
  loading: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState | undefined>(undefined);

/**
 * Wraps the app and exposes session state via `useSessionState()`.
 *
 * On mount (and whenever `refresh()` is called), asks the backend's
 * `GET /session/me` who the current session belongs to. This is a real,
 * server-verified check, not a client-only cookie presence check — the
 * session cookie is httpOnly and cannot be read from JavaScript at all.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setUser(await fetchSession());
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    setUser(null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <SessionContext.Provider value={{ user, isAuthenticated: user !== null, loading, logout, refresh }}>
      {children}
    </SessionContext.Provider>
  );
}

/**
 * Read the current session state, or trigger `logout()`. Must be called
 * from a descendant of `SessionProvider`.
 */
export function useSessionState(): SessionState {
  const context = useContext(SessionContext);

  if (context === undefined) {
    throw new Error("useSessionState must be used within a SessionProvider");
  }

  return context;
}
