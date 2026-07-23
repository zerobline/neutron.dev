from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.crew.skills_loader import (
    create_custom_skill,
    delete_custom_skill,
    get_project_skills_response,
    list_available_skills,
    update_project_skills,
)
from app.models import (
    ProjectSkillsResponse,
    ProjectSkillsUpdate,
    ProjectSkillSettings,
    SkillCatalogItem,
    SkillCreate,
    UserResponse,
)
from app.services import project_service

router = APIRouter(tags=["skills"])


def _ensure_project(project_id: str, owner_user_id: str):
    project = project_service.get_project(project_id, owner_user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/api/skills", response_model=list[SkillCatalogItem])
def list_builtin_skills(current_user: UserResponse = Depends(get_current_user)):
    _ = current_user
    items = []
    for skill in list_available_skills(project_id=None):
        items.append(
            SkillCatalogItem(
                name=skill["name"],
                description=skill["description"],
                source="builtin",
                recommended_agents=skill.get("recommended_agents") or [],
                enabled=False,
                agents=["all"],
                body_preview=skill.get("preview"),
            )
        )
    return items


@router.get("/api/projects/{project_id}/skills", response_model=ProjectSkillsResponse)
def get_project_skills(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    _ensure_project(project_id, current_user.id)
    return get_project_skills_response(project_id)


@router.put("/api/projects/{project_id}/skills", response_model=ProjectSkillsResponse)
def put_project_skills(
    project_id: str,
    data: ProjectSkillsUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    _ensure_project(project_id, current_user.id)
    return update_project_skills(project_id, ProjectSkillSettings(skills=data.skills))


@router.post("/api/projects/{project_id}/skills", response_model=ProjectSkillsResponse)
def post_custom_skill(
    project_id: str,
    data: SkillCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    _ensure_project(project_id, current_user.id)
    try:
        return create_custom_skill(project_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/projects/{project_id}/skills/{name}", response_model=ProjectSkillsResponse)
def remove_custom_skill(
    project_id: str,
    name: str,
    current_user: UserResponse = Depends(get_current_user),
):
    _ensure_project(project_id, current_user.id)
    try:
        return delete_custom_skill(project_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
