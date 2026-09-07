# Shared FastAPI dependencies: DB session, JWT auth, and workspace-membership / role guards.

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.workspace import WorkspaceMember

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user

def get_workspace_membership(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceMember:
    """
    Confirms current_user actually belongs to workspace_id, and returns
    their membership row (so routes can check .role too).

    Raises 404, not 403, when the user isn't a member. This is deliberate:
    403 would confirm the workspace_id exists and simply isn't accessible,
    letting an attacker enumerate valid workspace IDs by distinguishing
    403 (exists, no access) from 404 (doesn't exist) responses. Returning
    404 in both cases makes "not found" and "not yours" indistinguishable
    from the outside — this is the actual IDOR fix.
    """
    membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        .first()
    )

    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    return membership

def require_role(membership: WorkspaceMember, allowed_roles: list[str]):
    """
    Call this inside a route after get_workspace_membership, for
    endpoints that only owners/admins should be able to hit
    (e.g. deleting a workspace).

    Stays 403, not 404 — by this point membership is already confirmed
    (get_workspace_membership already ran), so the workspace's existence
    and the user's membership in it are not secret. This is a genuine
    permission failure, not an existence-disclosure risk, so 403 is the
    correct and honest status code here.
    """
    if membership.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed for your role")

def require_xhr_header(request: Request):
    """
    Reject state-changing cookie-authenticated requests that didn't come from
    our own frontend.

    refresh/logout are authenticated by an HttpOnly SameSite=None cookie (the
    cookie is what a cross-origin page would carry on a forged request). CORS
    stops a cross-origin page from *reading* the response, but it does NOT stop
    it from *sending* the request with the cookie attached — a bare cross-origin
    form submission or fetch() would silently succeed. Requiring a custom
    header closes that gap: browsers will not attach a custom header to a
    cross-origin request without first issuing a CORS preflight, and our CORS
    allowlist already rejects preflights from any origin that isn't the real
    frontend. So "missing header" here unambiguously means "not our frontend".

    Deliberately a single generic comparison with no server-side state and no
    token/session inspection — the 403 leaks nothing about the request.
    """
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed",
        )
