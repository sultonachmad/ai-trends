"use client";

/**
 * RBAC client store — React Context + hooks.
 *
 * Fetches /api/me once after the user is authenticated and stores the result
 * in a React Context so every component in the tree can read it without
 * prop-drilling.
 *
 * Usage:
 *   const { can, permissions, menus, menuGroups, roles, loading } = useRbac();
 *   const canEdit = useCan("feature_a:edit");
 *   <RbacGuard permission="roles:edit"><EditButton /></RbacGuard>
 *
 * `menus` — flat list of all visible MenuItem objects from /api/me.
 * `menuGroups` — hierarchical view: top-level items each with their children.
 *   Items with no children are standalone; items with children render as groups.
 *
 * The frontend NEVER computes privilege itself — it only reads from the
 * server-returned `permissions` array.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useSessionState } from "@/components/SessionProvider";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface MenuItem {
  id: number;
  name: string;
  path: string | null;
  icon: string | null;
  order: number;
  parent_id: number | null;
}

/** A top-level menu item with its children (empty array = standalone link). */
export interface MenuGroup {
  item: MenuItem;
  children: MenuItem[];
}

interface RbacState {
  id: number | null;
  email: string | null;
  roles: string[];
  permissions: string[];
  menus: MenuItem[];
  loading: boolean;
  error: string | null;
}

interface RbacContextValue extends RbacState {
  menuGroups: MenuGroup[];
  can: (code: string) => boolean;
  refresh: () => void;
}

const DEFAULT_STATE: RbacState = {
  id: null,
  email: null,
  roles: [],
  permissions: [],
  menus: [],
  loading: true,
  error: null,
};

const RbacContext = createContext<RbacContextValue>({
  ...DEFAULT_STATE,
  menuGroups: [],
  can: () => false,
  refresh: () => {},
});

export function RbacProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<RbacState>(DEFAULT_STATE);
  const [tick, setTick] = useState(0);

  const { isAuthenticated, loading: sessionLoading, user } = useSessionState();

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  // Stable key that changes when a different user is logged in.
  const userKey = isAuthenticated ? (user?.user_id ?? null) : null;

  useEffect(() => {
    // Wait until the session check resolves before touching RBAC state.
    if (sessionLoading) return;

    // Not authenticated — clear state immediately without fetching.
    if (!isAuthenticated || userKey === null) {
      setState({ ...DEFAULT_STATE, loading: false });
      return;
    }

    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));

    fetch(`${API_URL}/api/me`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`/api/me returned ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setState({
            id: data.id,
            email: data.email,
            roles: data.roles ?? [],
            permissions: data.permissions ?? [],
            menus: data.menus ?? [],
            loading: false,
            error: null,
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState((s) => ({
            ...s,
            loading: false,
            error:
              err instanceof Error
                ? err.message
                : "Failed to load RBAC context",
          }));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tick, userKey, isAuthenticated, sessionLoading]);

  const can = useCallback(
    (code: string) => state.permissions.includes(code),
    [state.permissions],
  );

  /** Build a tree: top-level items (parent_id === null) each with their children. */
  const menuGroups = useMemo<MenuGroup[]>(() => {
    const byParent = new Map<number | null, MenuItem[]>();
    for (const m of state.menus) {
      const key = m.parent_id ?? null;
      const list = byParent.get(key);
      if (list) {
        list.push(m);
      } else {
        byParent.set(key, [m]);
      }
    }
    const topLevel = (byParent.get(null) ?? [])
      .slice()
      .sort((a, b) => a.order - b.order);
    return topLevel.map((item) => ({
      item,
      children: (byParent.get(item.id) ?? [])
        .slice()
        .sort((a, b) => a.order - b.order),
    }));
  }, [state.menus]);

  const value = useMemo(
    () => ({ ...state, menuGroups, can, refresh }),
    [state, menuGroups, can, refresh],
  );

  return <RbacContext.Provider value={value}>{children}</RbacContext.Provider>;
}

export function useRbac(): RbacContextValue {
  return useContext(RbacContext);
}

/** Convenience hook: returns true if the user has `code`, false while loading. */
export function useCan(code: string): boolean {
  const { can } = useRbac();
  return can(code);
}
