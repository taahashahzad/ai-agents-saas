from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.core.permissions import Permission
from app.core.security import AuthenticatedUser
from app.dependencies.auth import get_current_user
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.schemas.business import BusinessCreate, BusinessOut, BusinessUpdate
from app.services import business_service
from app.services.membership_service import BusinessContext

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.post("", response_model=BusinessOut, status_code=201)
def create_business(payload: BusinessCreate, user: AuthenticatedUser = Depends(get_current_user),
                    db: Client = Depends(get_db)):
    return business_service.create_business(db, user, payload)


@router.get("", response_model=list[BusinessOut])
def list_businesses(user: AuthenticatedUser = Depends(get_current_user), db: Client = Depends(get_db)):
    return business_service.list_businesses(db, user)


@router.get("/{business_id}", response_model=BusinessOut)
def get_business(ctx: BusinessContext = Depends(require_permission(Permission.BUSINESS_VIEW))):
    return business_service.get_business(ctx)


@router.patch("/{business_id}", response_model=BusinessOut)
def update_business(payload: BusinessUpdate,
                    ctx: BusinessContext = Depends(require_permission(Permission.BUSINESS_EDIT)),
                    db: Client = Depends(get_db)):
    return business_service.update_business(db, ctx, payload)


@router.delete("/{business_id}", response_model=BusinessOut)
def archive_business(ctx: BusinessContext = Depends(require_permission(Permission.BUSINESS_ARCHIVE)),
                     db: Client = Depends(get_db)):
    """Soft delete: archives the business (status=archived) and returns it."""
    return business_service.archive_business(db, ctx)
