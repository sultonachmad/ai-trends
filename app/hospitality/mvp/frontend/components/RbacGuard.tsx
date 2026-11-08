"use client";

/**
 * RbacGuard — conditionally renders children based on a permission code.
 *
 * Usage:
 *   <RbacGuard permission="roles:edit">
 *     <EditButton />
 *   </RbacGuard>
 *
 *   // With a fallback element instead of null:
 *   <RbacGuard permission="roles:delete" fallback={<span>No access</span>}>
 *     <DeleteButton />
 *   </RbacGuard>
 *
 * Returns null (or `fallback`) while RBAC data is loading and when the user
 * lacks the permission. Never redirects — use `(authenticated)/layout.tsx`
 * (AuthGuard) for page-level redirection.
 */

import type { ReactNode } from "react";
import { useRbac } from "@/lib/rbac-store";

interface Props {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function RbacGuard({ permission, children, fallback = null }: Props) {
  const { can, loading } = useRbac();

  if (loading) return null;
  if (!can(permission)) return <>{fallback}</>;
  return <>{children}</>;
}
