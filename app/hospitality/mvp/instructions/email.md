<!-- Prefab: email v0.1.0 -->

# Email Prefab — Agent Instructions

This prefab adds **async SMTP email sending** to the base Next.js + FastAPI
skeleton. The core is `app/contact/email_service.py` — a reusable service for
building and sending MIME emails via any SMTP server. A sample contact form
endpoint (`POST /api/contact`) and frontend page demonstrate how to use it.
Requires `base-nextjs-fastapi` to be installed first.

## Where Things Live

```
backend/
  app/contact/__init__.py          # Package init
  app/contact/email_service.py     # Async SMTP sender (ContactMessage, send_contact_email)
  app/contact/schemas.py           # Sample contact form request/response schemas
  app/contact/router.py            # Sample POST /api/contact endpoint
frontend/
  app/sample-contact/page.tsx      # Sample contact form UI
```

`backend/app/main.py` is integrated at install time (marker `PREFAB:feature-routers`)
to register the sample contact router. Do not duplicate that registration.

`backend/app/config.py` is integrated at install time (marker `PREFAB:config-fields`)
to add SMTP settings fields. Do not duplicate those fields.

## Configuration

All SMTP settings come from environment variables (via the `PREFAB_` prefix in `config.py`):

| Env var | Default | Purpose |
|---------|---------|---------|
| `PREFAB_SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `PREFAB_SMTP_PORT` | `587` | SMTP server port (587 = STARTTLS) |
| `PREFAB_SMTP_USER` | *(empty)* | SMTP login username (also used as default "From" address) |
| `PREFAB_SMTP_PASSWORD` | *(empty)* | SMTP login password or app-specific password |
| `PREFAB_CONTACT_RECIPIENT` | *(empty)* | Default recipient; falls back to `SMTP_USER` if blank |

For Gmail, use an App Password — not your account password.

## Email Service (`email_service.py`)

The reusable core of this prefab. `send_contact_email` accepts a `ContactMessage`
dataclass and delivers it as a `multipart/alternative` MIME message (plaintext +
HTML). HTML fields are escaped with `html.escape()`.

SMTP is synchronous (`smtplib.SMTP` with STARTTLS, `timeout=30`), so
`send_contact_email` runs it in a thread via `asyncio.run_in_executor` to avoid
blocking the event loop. The timeout prevents a hung SMTP host from holding an
executor thread indefinitely.

### Sending Email From Your Own Code

Import and call `send_contact_email` directly, or build your own MIME message
using the same pattern:

```python
from app.contact.email_service import ContactMessage, send_contact_email

msg = ContactMessage(
    name="System",
    email="noreply@example.com",
    subject="Order Confirmation",
    body="Your order #1234 has been confirmed.",
)
await send_contact_email(msg)
```

For different email shapes (e.g. password reset, notification digest), add new
dataclasses and sender functions in `email_service.py` that reuse the same
`_send_sync` / `run_in_executor` pattern. Keep the SMTP connection short-lived
(one `with` block per send) — connection pooling adds complexity that is not
justified until send volume requires it.

## Sample: Contact Form Endpoint

The sample `POST /api/contact` endpoint and frontend page demonstrate using the
email service. Adapt or replace them for your use case.

### `POST /api/contact`

**Request:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "subject": "Hello",
  "message": "I'd like to learn more about your product."
}
```

**Success (200):**
```json
{ "success": true, "detail": "Message sent successfully" }
```

**Errors:**
- `503` — SMTP credentials not configured
- `500` — SMTP send failed
- `422` — Pydantic validation error

## ⚠️ Production TODOs

The sample `POST /api/contact` endpoint ships **unauthenticated and
unthrottled**. In production this is an open email relay to
`CONTACT_RECIPIENT`. Before deploying to a public environment:

1. **Add authentication** — put the endpoint behind your auth middleware
2. **Add rate limiting** — per-IP or per-user throttle to prevent abuse
3. **Consider a queue** — `run_in_executor` uses the default thread pool;
   high-volume sends should use a task queue (Celery, ARQ, etc.)

## Rules

### DO
- Set `PREFAB_SMTP_USER` and `PREFAB_SMTP_PASSWORD` in `.env` before testing
- Import from `app.contact.email_service` when sending emails from other modules
- Add rate limiting to any public-facing email endpoint in production

### DO NOT
- Do not call `smtplib` directly from route handlers — always go through
  `email_service` (which runs SMTP in a thread pool)
- Do not store SMTP credentials in source code — they come from environment
  variables via `app/config.py`
