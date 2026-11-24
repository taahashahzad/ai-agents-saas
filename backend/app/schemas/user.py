from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class UserUpsert(BaseModel):
    """uid and email are NOT accepted here: they come from the verified token."""
    model_config = ConfigDict(extra="forbid")
    display_name: DisplayName | None = None


class UserOut(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    platform_role: str | None = None  # "system_admin" or null; comes from the token, never stored
    created_at: datetime
    updated_at: datetime | None = None
