import logging

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.contact.email_service import ContactMessage, send_contact_email
from app.contact.schemas import ContactRequest, ContactResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("", response_model=ContactResponse)
async def send_contact(body: ContactRequest) -> ContactResponse:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise HTTPException(status_code=503, detail="Email service is not configured")

    msg = ContactMessage(
        name=body.name,
        email=body.email,
        subject=body.subject,
        body=body.message,
    )

    try:
        await send_contact_email(msg)
    except Exception:
        logger.exception("Failed to send contact email")
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again later.",
        )

    return ContactResponse(success=True, detail="Message sent successfully")
