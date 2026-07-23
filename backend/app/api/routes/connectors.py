from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.crew.connectors import load_project_connectors, save_project_connectors
from app.models import ProjectConnectorSettings, UserResponse
from app.services import project_service

router = APIRouter(prefix="/api/projects/{project_id}/connectors", tags=["connectors"])


def _ensure_project(project_id: str, owner_user_id: str):
    project = project_service.get_project(project_id, owner_user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=ProjectConnectorSettings)
def get_project_connectors(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    _ensure_project(project_id, current_user.id)
    return load_project_connectors(project_id)


@router.put("", response_model=ProjectConnectorSettings)
def update_project_connectors(project_id: str, data: ProjectConnectorSettings, current_user: UserResponse = Depends(get_current_user)):
    _ensure_project(project_id, current_user.id)
    return save_project_connectors(project_id, data)
