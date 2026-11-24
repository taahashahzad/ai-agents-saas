from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.emails import is_valid_email, normalize_email


class InvitableRole(str, Enum):
    """Owners cannot be invited."""
    admin = "admin"
    member = "member"


class InvitationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"  # derived at read time: pending + past expires_at


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    role: InvitableRole = InvitableRole.member

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        email = normalize_email(value)
        if not email or not is_valid_email(email):
            raise ValueError("A valid email address is required.")
        return email


class InvitationOut(BaseModel):
    invitation_id: str
    business_id: str
    business_name: str | None = None
    email: str
    role: str
    invited_by: str
    status: InvitationStatus
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
