/**
 * NextAuth.js v5 configuration.
 *
 * This is the FULL auth configuration — providers, session strategy, and
 * all callbacks — and is the single source of truth for the NextAuth
 * instance used server-side. `frontend/lib/auth.ts` imports `auth` from
 * here; `app/api/auth/[...nextauth]/route.ts` re-exports `GET` and `POST`
 * from here and nothing else, because a Next.js route file may export only
 * HTTP method handlers and route segment config, so `handlers`, `auth`,
 * `signIn` and `signOut` cannot be exported from it.
 *
 * This module must only be imported from Node.js-runtime code, because the
 * providers the provider prefabs splice in here depend on `openid-client`
 * (Node-only APIs).
 * `@/lib/auth` imports it, so `middleware.ts` must import neither.
 * (`middleware.ts` builds its own provider-free NextAuth instance from
 * `auth.config.ts`.)
 */
import NextAuth, { type NextAuthConfig } from "next-auth";
import { SignJWT } from "jose";
import Google from "next-auth/providers/google";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
// PREFAB:route-imports

import { authConfig } from "@/auth.config";

// Backend-verifiable token minting.
//
// The FastAPI backend authenticates requests by verifying an HS256 JWT signed
// with its `PREFAB_SECRET_KEY` (see backend `app/auth/jwt.py`). We mint exactly
// that token here — the ONE place every provider (whichever provider prefabs
// are installed, and the credentials prefab) funnels through after a successful
// sign-in — so the whole app
// shares a single token model. `NEXTAUTH_SECRET` MUST equal the backend's
// `PREFAB_SECRET_KEY` for verification to succeed.
const BACKEND_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

async function mintBackendToken(claims: {
  sub: string;
  email?: string | null;
  name?: string | null;
}): Promise<string> {
  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET ?? "");
  return new SignJWT({
    email: claims.email ?? undefined,
    name: claims.name ?? undefined,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(claims.sub)
    .setIssuedAt()
    .setExpirationTime(`${BACKEND_TOKEN_TTL_SECONDS}s`)
    .sign(secret);
}

// No provider is registered here. Each provider prefab (auth-oauth2-google,
// auth-oauth2-microsoft, auth-credentials) splices its import at
// PREFAB:route-imports and its providers.push(...) at PREFAB:route-providers.
const providers: NextAuthConfig["providers"] = [];

// Test-only mock IdP — exercises the full callback pipeline without a real
// OAuth provider.  NEVER enable in production.
if (process.env.NODE_ENV === "test") {
  // Dynamic import keeps credentials provider out of production bundles.
  const CredentialsProvider = (await import("next-auth/providers/credentials"))
    .default;
  providers.push(
    CredentialsProvider({
      id: "credentials-test",
      name: "Test Login",
      credentials: {
        email: { label: "Email", type: "email" },
        name: { label: "Name", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email) return null;
        return {
          id: `test-${credentials.email}`,
          email: credentials.email as string,
          name: (credentials.name as string) || "Test User",
        };
      },
    }),
  );
}

providers.push(
  Google({
    clientId: process.env.GOOGLE_CLIENT_ID ?? "",
    clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
  }),
);
providers.push(
  MicrosoftEntraID({
    clientId: process.env.AZURE_AD_CLIENT_ID ?? "",
    clientSecret: process.env.AZURE_AD_CLIENT_SECRET ?? "",
    issuer: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID ?? ""}/v2.0`,
  }),
);
// PREFAB:route-providers

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt" },
  providers,
  callbacks: {
    ...authConfig.callbacks,
    async jwt({ token, account, profile }) {
      if (account) {
        token.provider = account.provider;
      }
      if (profile) {
        token.name = profile.name ?? token.name;
        token.email = profile.email ?? token.email;
      }
      // Microsoft Entra ID may return the email under non-standard claim
      // names (mail, upn, preferred_username) depending on tenant config.
      if (!token.email && profile && typeof profile === "object") {
        const p = profile as Record<string, unknown>;
        const fallback = p.mail ?? p.upn ?? p.preferred_username;
        if (typeof fallback === "string") token.email = fallback;
      }
      // Mint the backend-verifiable token on fresh sign-in (when `account` is
      // present) and reuse it on subsequent calls. This is the single point
      // every provider passes through, so each installed provider yields a
      // token the FastAPI backend accepts.
      if (account && typeof token.sub === "string") {
        token.accessToken = await mintBackendToken({
          sub: token.sub,
          email: typeof token.email === "string" ? token.email : null,
          name: typeof token.name === "string" ? token.name : null,
        });
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = typeof token.sub === "string" ? token.sub : "";
      }
      // Expose the backend token so the API client can send it as a Bearer
      // header (see `@/lib/auth-token` + `@/lib/api-client`).
      session.accessToken =
        typeof token.accessToken === "string" ? token.accessToken : undefined;
      return session;
    },
  },
});

export const { GET, POST } = handlers;
