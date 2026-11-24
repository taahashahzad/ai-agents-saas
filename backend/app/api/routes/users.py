from fastapi import APIRouter, Depends, Response
from google.cloud.firestore import Client

from app.core.errors import NotFoundError
from app.core.security import AuthenticatedUser
from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.schemas.user import UserOut, UserUpsert
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: AuthenticatedUser = Depends(get_current_user), db: Client = Depends(get_db)):
    profile = user_service.get_profile(db, user)
    if profile is None:
        raise NotFoundError("User profile not found. Create it with POST /api/v1/users/me.",
                            code="profile_not_found")
    return profile


@router.post("/me", response_model=UserOut, status_code=201)
def upsert_me(
    response: Response,
    payload: UserUpsert | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """201 when the profile is created, 200 when an existing profile is updated."""
    profile, created = user_service.upsert_profile(db, user, payload or UserUpsert())
    if not created:
        response.status_code = 200
    return profile
