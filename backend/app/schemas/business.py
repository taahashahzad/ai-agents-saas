from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


class BusinessType(str, Enum):
    restaurant = "restaurant"
    clinic = "clinic"
    school = "school"


class BusinessRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class BusinessStatus(str, Enum):
    active = "active"
    archived = "archived"


NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DescriptionStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class BusinessCreate(BaseModel):
    # extra="forbid": owner_id, role, status, etc. sent by a client are rejected (422).
    model_config = ConfigDict(extra="forbid")
    name: NameStr
    business_type: BusinessType
    description: DescriptionStr = ""


class BusinessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NameStr | None = None
    business_type: BusinessType | None = None  # owner-controlled
    description: DescriptionStr | None = None

    @model_validator(mode="after")
    def _at_least_one_non_null_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' must not be null.")
        return self


class BusinessOut(BaseModel):
    id: str
    name: str
    business_type: BusinessType
    description: str = ""
    owner_id: str
    status: BusinessStatus
    created_at: datetime
    updated_at: datetime
    role: BusinessRole  # the caller's role in this business
