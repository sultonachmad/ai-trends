/**
 * Public nav links -- routes of pages outside `app/(authenticated)/`.
 *
 * `useRbac()` returns no menus until the visitor signs in, so `Nav`, `Sidebar`
 * and the homepage render this array for anonymous visitors. Never list a
 * route under `(authenticated)/` here, nor `/` or `/login` (the nav already
 * links both).
 */
export const PUBLIC_LINKS: { href: string; label: string }[] = [];
