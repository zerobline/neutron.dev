from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from app.models import ProjectCreate, ProjectResponse, UserResponse
from app.crew.checkpoints import list_checkpoints
from app.crew.stacks import normalize_stack
from app.services import project_service
from app.services.project_runtime import runtime_manager

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
def create_project(data: ProjectCreate, current_user: UserResponse = Depends(get_current_user)):
    return project_service.create_project(data, current_user.id)


@router.get("", response_model=list[ProjectResponse])
def list_projects(current_user: UserResponse = Depends(get_current_user)):
    return project_service.list_projects(current_user.id)


@router.get("/{project_id}/download")
def download_project(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    archive = project_service.build_project_zip(project_id)
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'},
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    if not project_service.delete_project(project_id, current_user.id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@router.get("/{project_id}/files")
def get_project_files(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_service.get_project_files(project_id)


@router.get("/{project_id}/messages")
def get_project_messages(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_service.get_messages(project_id)


@router.get("/{project_id}/checkpoints")
def get_project_checkpoints(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    checkpoints = list_checkpoints(project_id)
    return {
        "checkpoints": checkpoints,
        "latest": checkpoints[0]["location"] if checkpoints else None,
    }


@router.get("/{project_id}/runtime")
def get_project_runtime(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return runtime_manager.get_status(project_id)


@router.post("/{project_id}/runtime/start")
def start_project_runtime(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if normalize_stack(project.stack) != "nextjs":
        raise HTTPException(
            status_code=400,
            detail="Live runtime preview is only available for Next.js projects.",
        )
    try:
        return runtime_manager.start(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{project_id}/runtime/stop")
def stop_project_runtime(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return runtime_manager.stop(project_id)
