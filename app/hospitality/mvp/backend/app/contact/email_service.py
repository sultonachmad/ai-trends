import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from app.config import settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class ContactMessage:
    name: str
    email: str
    subject: str
    body: str


def _build_mime(msg: ContactMessage) -> MIMEMultipart:
    mime = MIMEMultipart("alternative")
    mime["From"] = settings.SMTP_USER
    mime["To"] = settings.CONTACT_RECIPIENT or settings.SMTP_USER
    mime["Subject"] = f"Contact Form: {msg.subject}"
    mime["Reply-To"] = msg.email

    text_body = (
        f"Name: {msg.name}\n"
        f"Email: {msg.email}\n"
        f"Subject: {msg.subject}\n\n"
        f"{msg.body}"
    )

    html_body = (
        "<html><body>"
        f"<p><strong>Name:</strong> {escape(msg.name)}</p>"
        f"<p><strong>Email:</strong> {escape(msg.email)}</p>"
        f"<p><strong>Subject:</strong> {escape(msg.subject)}</p>"
        "<hr>"
        f"<p>{escape(msg.body)}</p>"
        "</body></html>"
    )

    mime.attach(MIMEText(text_body, "plain"))
    mime.attach(MIMEText(html_body, "html"))
    return mime


def _send_sync(msg: ContactMessage) -> None:
    mime = _build_mime(msg)
    recipient = settings.CONTACT_RECIPIENT or settings.SMTP_USER
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, recipient, mime.as_string())


async def send_contact_email(msg: ContactMessage) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _send_sync, msg)
