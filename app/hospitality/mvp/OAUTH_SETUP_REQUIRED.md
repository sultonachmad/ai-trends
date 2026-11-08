# OAuth Provider Setup Required

This workspace uses third-party OAuth login. The OAuth provider(s)
must be configured in their admin console before login will work.

---

## Google OAuth

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create or select an OAuth 2.0 Client ID (Web application)
3. Set the following values:

| Setting | Value |
|---------|-------|
| Authorized JavaScript origins | `http://localhost:3100` |
| Authorized redirect URIs | `http://localhost:3100/api/auth/callback/google` |

4. Copy the Client ID and Client Secret into your `.env.local`:

```env
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
```

---

## Microsoft Entra ID (formerly Azure AD)

### Entra Admin Setup

1. Go to [Microsoft Entra admin center](https://entra.microsoft.com/) → App registrations
2. Create or select an app registration
3. Under Authentication → Web → Redirect URIs, add:

   `http://localhost:3100/api/auth/callback/microsoft-entra-id`

4. Copy the Application (client) ID, Directory (tenant) ID, and a client secret into `.env.local`:

```env
AZURE_AD_CLIENT_ID=<application-client-id>
AZURE_AD_CLIENT_SECRET=<client-secret-value>
AZURE_AD_TENANT_ID=<directory-tenant-id>
```

---

## Shared Secret

`NEXTAUTH_SECRET` must equal the backend's `PREFAB_SECRET_KEY`.
Generate a random value and set both:

```env
# frontend/.env.local
NEXTAUTH_SECRET=<random-secret>

# backend/.env
PREFAB_SECRET_KEY=<same-random-secret>
```

---

## Acknowledgment

**This file must be acknowledged by the user before any OAuth task is
marked complete.** The AI agent cannot verify provider console setup —
only a human with access to the Google Cloud / Entra admin console can.
