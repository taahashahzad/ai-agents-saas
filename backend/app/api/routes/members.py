from fastapi import APIRouter, Depends, Response
from google.cloud.firestore import Client

from app.core.permissions import Permission
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.schemas.member import MemberOut, MemberRoleUpdate
from app.services import membership_service
from app.services.membership_service import BusinessContext

router = APIRouter(prefix="/businesses/{business_id}/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
def list_members(ctx: BusinessContext = Depends(require_permission(Permission.MEMBERS_VIEW)),
                 db: Client = Depends(get_db)):
    return membership_service.list_members(db, ctx)


@router.patch("/{uid}/role", response_model=MemberOut)
def change_member_role(uid: str, payload: MemberRoleUpdate,
                       ctx: BusinessContext = Depends(require_permission(Permission.MEMBERS_CHANGE_ROLE)),
                       db: Client = Depends(get_db)):
    """Owner only. member <-> admin. Ownership cannot be assigned here."""
    return membership_service.change_role(db, ctx, uid, payload.role)


@router.delete("/{uid}", status_code=204, response_class=Response)
def remove_member(uid: str,
                  ctx: BusinessContext = Depends(require_permission(Permission.MEMBERS_REMOVE)),
                  db: Client = Depends(get_db)):
    """Owner removes admins/members; admin removes members. 204 No Content."""
    membership_service.remove_member(db, ctx, uid)
    return Response(status_code=204)
