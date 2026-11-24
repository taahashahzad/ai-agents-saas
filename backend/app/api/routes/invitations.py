from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.core.config import Settings
from app.core.permissions import Permission
from app.core.security import InviteeIdentity
from app.dependencies.auth import get_invitee
from app.dependencies.business import require_permission
from app.dependencies.db import get_db
from app.dependencies.settings import get_app_settings
from app.schemas.invitation import InvitationCreate, InvitationOut
from app.services import invitation_service
from app.services.membership_service import BusinessContext

# Business-side: owner/admin manage invitations of one business.
business_router = APIRouter(prefix="/businesses/{business_id}/invitations", tags=["invitations"])

# Invitee-side: the signed-in user's own invitations.
router = APIRouter(prefix="/invitations", tags=["invitations"])


@business_router.post("", response_model=InvitationOut, status_code=201)
def create_invitation(payload: InvitationCreate,
                      ctx: BusinessContext = Depends(require_permission(Permission.INVITATIONS_CREATE)),
                      db: Client = Depends(get_db), settings: Settings = Depends(get_app_settings)):
    """Owner may invite admin/member; admin may invite member only."""
    return invitation_service.create_invitation(db, ctx, payload, settings.invitation_ttl_days)


@business_router.get("", response_model=list[InvitationOut])
def list_business_invitations(
        ctx: BusinessContext = Depends(require_permission(Permission.INVITATIONS_VIEW)),
        db: Client = Depends(get_db)):
    return invitation_service.list_business_invitations(db, ctx)


@router.get("", response_model=list[InvitationOut])
def list_my_invitations(invitee: InviteeIdentity = Depends(get_invitee), db: Client = Depends(get_db)):
    """Pending, unexpired invitations addressed to the authenticated user's email."""
    return invitation_service.list_my_invitations(db, invitee)


@router.post("/{invitation_id}/accept", response_model=InvitationOut)
def accept_invitation(invitation_id: str, invitee: InviteeIdentity = Depends(get_invitee),
                      db: Client = Depends(get_db)):
    return invitation_service.accept_invitation(db, invitee, invitation_id)


@router.post("/{invitation_id}/decline", response_model=InvitationOut)
def decline_invitation(invitation_id: str, invitee: InviteeIdentity = Depends(get_invitee),
                       db: Client = Depends(get_db)):
    return invitation_service.decline_invitation(db, invitee, invitation_id)
