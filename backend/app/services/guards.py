from app.core.errors import ConflictError
from app.schemas.business import BusinessStatus
from app.services.membership_service import BusinessContext


def require_active_business(ctx: BusinessContext) -> None:
    """Archived businesses are read-only."""
    if ctx.business.get("status") == BusinessStatus.archived.value:
        raise ConflictError("Archived businesses cannot be modified.", code="business_archived")
