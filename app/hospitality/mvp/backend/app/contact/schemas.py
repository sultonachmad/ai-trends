import re

from pydantic import BaseModel, field_validator

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 320
MAX_SUBJECT_LENGTH = 500
MAX_MESSAGE_LENGTH = 50_000


def _reject_newlines(value: str, field_name: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError(f"{field_name} must not contain newlines")
    return value


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if len(v) > MAX_EMAIL_LENGTH:
            raise ValueError(f"Email must be at most {MAX_EMAIL_LENGTH} characters")
        if not EMAIL_PATTERN.fullmatch(v):
            raise ValueError("Invalid email address")
        return v.lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Name must be at most {MAX_NAME_LENGTH} characters")
        return _reject_newlines(v, "Name")

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Subject must not be empty")
        if len(v) > MAX_SUBJECT_LENGTH:
            raise ValueError(f"Subject must be at most {MAX_SUBJECT_LENGTH} characters")
        return _reject_newlines(v, "Subject")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message must not be empty")
        if len(v) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message must be at most {MAX_MESSAGE_LENGTH} characters")
        return v


class ContactResponse(BaseModel):
    success: bool
    detail: str
