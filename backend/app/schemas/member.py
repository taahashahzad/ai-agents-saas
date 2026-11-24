from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.business import BusinessRole


class MemberOut(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    role: BusinessRole
    joined_at: datetime | None = None


class MemberRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "owner" parses, but is always refused by the service (ownership transfer is not supported).
    role: BusinessRole
