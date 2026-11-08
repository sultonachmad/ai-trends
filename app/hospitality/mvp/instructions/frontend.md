<!-- Prefab: base-frontend-nextjs v0.3.0 -->

# Frontend Agent Instructions — Next.js 15 + Tailwind CSS

You are building the **frontend** of a full-stack project using Next.js 15 (App Router) and Tailwind CSS 4.

## Project Structure

```
frontend/
  app/              # App Router pages and layouts
  components/       # Shared UI components
  lib/              # Utilities, API client, hooks
  styles/           # globals.css (Tailwind directives)
  public/           # Static assets
```

## Rules

### DO
- Use `app/` directory (App Router) for pages — never `pages/`
- Use Server Components by default; add `'use client'` only when needed (state, effects, event handlers)
- Use `fetch()` with the backend URL from env (`NEXT_PUBLIC_API_URL`) for API calls
- Use components/ the shared UI components is first priority, ask if need create new one
- Use Tailwind utility classes for ALL styling — never write custom CSS (second priorty after use components)

### DO NOT
- Do not use `getServerSideProps` or `getStaticProps` — use App Router patterns
- Do not hardcode URLs — use env vars (`NEXT_PUBLIC_API_URL`)
- Do not create custom element if components is exist
- Do not create custom CSS files or `<style>` tags — use Tailwind only
- Do not create wrapper components for HTML elements that Tailwind can style directly
- Do not add dependencies without listing them in the response
- Do not leave a new feature page unreachable — always add a navigation entry (see **Navigation Menu Pattern**)

## Navigation Menu Pattern

After creating a new feature page, add a nav entry in `components/Nav.tsx` if one does not exist:

```tsx
type NavLink = { href: string; label: string };

const links: NavLink[] = [
  { href: "/", label: "Home" },
  { href: "/products", label: "Products" },   // ← add new feature here
];
```

- Only add links for top-level features — not nested sub-pages (`/products/[id]`)
- Order: Home first, features, then utility pages (Settings, About) last — unless the workspace's `CLAUDE.md` has the "Designed menu placement" rule, whose designed menu order wins
- If the project uses a sidebar instead, apply the same rule to that component

## Link Landing Pages

A page reached from a link in an email (invite, password reset, email verification) reads its token from a path segment: `app/invite/[token]/page.tsx`. The page stays public (outside `app/(authenticated)/`), since the person opening the link is not logged in. Read it with `useParams()` in a client component, or `const { token } = await params;` in a server page. Never read the token from `?token=` on a static page such as `app/invite/page.tsx`: that page opens with no token whenever someone visits it directly.

## Authenticated Pages

Pages that require login **must** be created inside `app/(authenticated)/`. Pages outside this folder are public.

```
app/
  (authenticated)/     # ← protected: requires login
    dashboard/page.tsx
    settings/page.tsx
  login/page.tsx       # ← public: no auth required
  page.tsx             # ← public
```

- If unsure whether a page needs auth, ask the user before creating it
- The nav link href stays the same regardless of the route group — `(authenticated)` is invisible in the URL

## Dynamic Route Names

Next.js refuses to start when two `[…]` folders at the same URL level have different names (`app/candidates/[candidateId]/` beside `app/candidates/[jobDescriptionId]/`). Route groups do not count: `app/(authenticated)/candidates/[a]/` and `app/candidates/[b]/` are the same level.

- Before creating a `[…]` folder, list the folders already at that level, inside every route group
- If one is there and the page is about the same thing, reuse its name (`[candidateId]`)
- If the page is about a different thing, give it its own path: `app/job-descriptions/[id]/scores/page.tsx`, not `app/candidates/[jobDescriptionId]/scores/page.tsx`
