/**
 * Module augmentation for the backend-verifiable access token this prefab
 * mints in the NextAuth `jwt` callback and exposes on the session.
 *
 * `accessToken` is an HS256 JWT signed with `NEXTAUTH_SECRET`; the FastAPI
 * backend verifies it with the SAME shared secret (`PREFAB_SECRET_KEY`) in
 * `app/auth/jwt.py`. The API client reads it via `session.accessToken` and
 * sends it as `Authorization: Bearer <token>`.
 */
import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
  }
}
