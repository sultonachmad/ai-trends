/**
 * Edge-safe NextAuth config — deliberately excludes `providers`.
 *
 * Providers such as Google or Microsoft pull in `openid-client`, which relies on Node.js
 * APIs unavailable in the Edge runtime. `middleware.ts` runs at the edge,
 * so it must only ever use a NextAuth instance built from THIS config, not
 * the full one in `lib/nextauth.ts` (where the provider
 * prefabs splice their providers, which is fine there because that module is only
 * imported by the route handler and by server code, which run on the Node.js runtime).
 *
 * The full NextAuth config spreads this object and adds `providers` on top —
 * see `lib/nextauth.ts`.
 */
import type { NextAuthConfig } from "next-auth";

export const authConfig: NextAuthConfig = {
  pages: {
    signIn: "/login",
  },
  providers: [],
  callbacks: {
    authorized({ auth, request }) {
      if (auth?.user) return true;
      if (request.cookies.has("prefab_session")) return true;
      return false;
    },
  },
};
