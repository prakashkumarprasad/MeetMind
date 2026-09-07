# Authentication routes: signup, login, Google OAuth, refresh-token rotation, logout, and current user.

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse, GoogleAuthRequest

from app.db.session import get_db
from app.api.deps import get_current_user, require_xhr_header
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.rate_limit import get_rate_limit_info, increment_rate_limit
from app.core.config import settings
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.refresh_token_family import RefreshTokenFamily
from datetime import datetime, timezone

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"

SIGNUP_RATE_LIMIT_MAX = 5
SIGNUP_RATE_LIMIT_WINDOW_SECONDS = 900

@router.post("/signup", response_model=TokenResponse)
def signup(data: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)):

    client_ip = request.client.host if request.client else "unknown"
    ip_limited, ip_retry, _ = get_rate_limit_info(
        f"signup:{client_ip}",
        max_attempts=SIGNUP_RATE_LIMIT_MAX,
        window_seconds=SIGNUP_RATE_LIMIT_WINDOW_SECONDS,
    )
    if ip_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signups from this address, try again later",
            headers={"Retry-After": str(ip_retry)},
        )

    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    db.flush()

    workspace = Workspace(name=f"{data.full_name or data.email}'s workspace")
    db.add(workspace)
    db.flush()

    membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(membership)

    db.commit()

    increment_rate_limit(
        f"signup:{client_ip}",
        max_attempts=SIGNUP_RATE_LIMIT_MAX,
        window_seconds=SIGNUP_RATE_LIMIT_WINDOW_SECONDS,
    )

    return _issue_new_family(user.id, response, db)

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    ip_limited, ip_retry, _ = get_rate_limit_info(f"login:{client_ip}", max_attempts=5, window_seconds=900)
    email_limited, email_retry, _ = get_rate_limit_info(f"login:{data.email}", max_attempts=5, window_seconds=900)
    if ip_limited or email_limited:
        retry_after = max(ip_retry, email_retry)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.email == data.email).first()

    if user is None or user.hashed_password is None:

        increment_rate_limit(f"login:{client_ip}", max_attempts=5, window_seconds=900)
        increment_rate_limit(f"login:{data.email}", max_attempts=5, window_seconds=900)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(data.password, user.hashed_password):

        increment_rate_limit(f"login:{client_ip}", max_attempts=5, window_seconds=900)
        increment_rate_limit(f"login:{data.email}", max_attempts=5, window_seconds=900)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return _issue_new_family(user.id, response, db)

@router.post("/google", response_model=TokenResponse)
def google_auth(data: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)):
    try:
        payload = google_id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    google_id = payload["sub"]
    email = payload.get("email")
    full_name = payload.get("name")

    if not payload.get("email_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email not verified")

    user = db.query(User).filter(User.google_id == google_id).first()

    if user is None and email:

        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            user.google_id = google_id
            db.flush()

    if user is None:
        user = User(email=email, google_id=google_id, full_name=full_name, hashed_password=None)
        db.add(user)
        db.flush()

        workspace = Workspace(name=f"{full_name or email}'s workspace")
        db.add(workspace)
        db.flush()

        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        db.add(membership)

    db.commit()

    return _issue_new_family(user.id, response, db)

@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _xhr: None = Depends(require_xhr_header),
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    family = (
        db.query(RefreshTokenFamily)
        .filter(
            RefreshTokenFamily.family_id == payload.get("family"),
            RefreshTokenFamily.user_id == user.id,
        )
        .first()
    )
    if family is None or family.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    presented_jti = str(payload.get("jti"))
    if family.last_jti is not None and presented_jti != str(family.last_jti):
        now = datetime.now(timezone.utc)
        rotated = family.last_rotated_at
        is_within_grace = (
            rotated is not None
            and (now - rotated).total_seconds() <= settings.REFRESH_REUSE_GRACE_SECONDS
        )
        if not is_within_grace:
            family.revoked = True
            family.revoked_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reuse detected; session revoked",
            )

    return _issue_tokens_for_family(user.id, family, response, db)

def _issue_new_family(user_id, response: Response, db: Session) -> TokenResponse:
    """Initial login/signup/Google: create a brand-new refresh-token family."""
    family = RefreshTokenFamily(user_id=user_id)
    db.add(family)
    db.commit()
    return _issue_tokens_for_family(user_id, family, response, db)

def _issue_tokens_for_family(
    user_id, family: RefreshTokenFamily, response: Response, db: Session,
) -> TokenResponse:
    """Issue a fresh refresh token within an existing family (rotation) and
    record its jti so a replay of an older token is detectable."""
    jti = uuid.uuid4()
    family.last_jti = jti
    family.last_rotated_at = datetime.now(timezone.utc)
    family.revoked = False
    family.revoked_at = None

    refresh_token = create_refresh_token(str(user_id), str(family.family_id), jti)

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="none" if settings.ENVIRONMENT != "development" else "lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    db.commit()

    return TokenResponse(access_token=create_access_token(str(user_id)))

@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _xhr: None = Depends(require_xhr_header),
):

    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            payload = None
        if payload and payload.get("type") == "refresh" and payload.get("family"):
            family = (
                db.query(RefreshTokenFamily)
                .filter(RefreshTokenFamily.family_id == payload["family"])
                .first()
            )

            try:
                cookie_user = uuid.UUID(str(payload.get("sub")))
            except (ValueError, TypeError):
                cookie_user = None
            if family is not None and cookie_user is not None and cookie_user == family.user_id:
                family.revoked = True
                family.revoked_at = datetime.now(timezone.utc)
                db.commit()

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="none" if settings.ENVIRONMENT != "development" else "lax",
    )
    return {"message": "Logged out"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
    )
