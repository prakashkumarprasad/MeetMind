# Workspace routes: listing the caller's workspaces.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    role: str

    class Config:
        from_attributes = True

@router.get("", response_model=list[WorkspaceSummary])
def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == current_user.id)
        .all()
    )

    result = []
    for membership in memberships:
        workspace = db.get(Workspace, membership.workspace_id)
        result.append(WorkspaceSummary(id=workspace.id, name=workspace.name, role=membership.role))

    return result
