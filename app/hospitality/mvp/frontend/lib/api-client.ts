/**
 * Generic typed CRUD API client factory for the crud-scaffold prefab.
 *
 * Call `createEntityApi<T>(basePath)` once per entity to get a small, typed
 * client — `list`, `get`, `create`, `update`, `remove` — that talks to
 * `${NEXT_PUBLIC_API_URL}${basePath}`, matching the prefix passed to the
 * backend's `create_crud_router(...)`.
 *
 * Auth: every request sends the session cookie (`credentials: "include"`).
 * The cookie authenticates routes that use auth-session's session dependency
 * (`get_current_user` from `app.session.dependencies`). Routes that use
 * auth-oauth2's `get_current_user` (`app.auth.dependencies`) read only an
 * `Authorization: Bearer <token>` header. This client sends that header when
 * an auth prefab has registered a token provider (see `@/lib/auth-token`), but
 * no prefab registers one yet, so those routes still answer 401. Use this
 * client for every protected call — a raw `fetch` without
 * `credentials: "include"` gets a 401.
 */

import { getAuthToken } from "@/lib/auth-token";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface EntityApi<T> {
  list: (query?: string) => Promise<T[]>;
  get: (id: number | string) => Promise<T>;
  create: (data: Partial<T>) => Promise<T>;
  update: (id: number | string, data: Partial<T>) => Promise<T>;
  remove: (id: number | string) => Promise<void>;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      return body.detail;
    }
    return JSON.stringify(body);
  } catch {
    return (
      response.statusText || `Request failed with status ${response.status}`
    );
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/**
 * Build a typed CRUD client for the entity mounted at `basePath`
 * (e.g. `/widgets`).
 */
export function createEntityApi<T>(basePath: string): EntityApi<T> {
  return {
    list: (query?: string) => {
      const search = query ? `?q=${encodeURIComponent(query)}` : "";
      return request<T[]>(`${basePath}${search}`);
    },

    get: (id: number | string) => request<T>(`${basePath}/${id}`),

    create: (data: Partial<T>) =>
      request<T>(basePath, {
        method: "POST",
        body: JSON.stringify(data),
      }),

    update: (id: number | string, data: Partial<T>) =>
      request<T>(`${basePath}/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),

    remove: (id: number | string) =>
      request<void>(`${basePath}/${id}`, {
        method: "DELETE",
      }),
  };
}
