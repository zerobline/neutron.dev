import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.auth.dependencies import get_current_user
from app.config import settings
from app.models import UserResponse
from app.services import project_service

router = APIRouter(prefix="/api/projects/{project_id}/uploads", tags=["uploads"])

MAX_FILE_SIZE = settings.max_upload_file_bytes
MAX_PROJECT_SIZE = settings.max_upload_project_bytes
MAX_FILES_PER_PROJECT = settings.max_upload_files_per_project
CHUNK_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".css",
    ".csv",
    ".gif",
    ".html",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".webp",
    ".xml",
    ".yaml",
    ".yml",
}
ALLOWED_CONTENT_TYPES = {
    "application/json",
    "application/pdf",
    "application/xml",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "image/webp",
    "text/css",
    "text/csv",
    "text/html",
    "text/javascript",
    "text/markdown",
    "text/plain",
    "text/xml",
}


def sanitize_filename(filename: str | None) -> str:
    name = Path(filename or "unnamed.txt").name or "unnamed.txt"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return safe or "unnamed.txt"


def validate_upload_type(filename: str, content_type: str | None) -> None:
    suffix = Path(filename).suffix.lower()
    normalized_type = (content_type or "text/plain").split(";", 1)[0].strip().lower()
    if suffix not in ALLOWED_EXTENSIONS or normalized_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported file type")


def resolve_upload_path(upload_dir: Path, filename: str) -> Path:
    dest = (upload_dir / filename).resolve()
    try:
        dest.relative_to(upload_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename") from exc
    return dest


@router.post("")
async def upload_file(project_id: str, file: UploadFile = File(...), current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    upload_dir = settings.projects_dir / project_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    existing_files = [path for path in upload_dir.iterdir() if path.is_file()]
    if len(existing_files) >= MAX_FILES_PER_PROJECT:
        raise HTTPException(status_code=413, detail=f"Project upload limit is {MAX_FILES_PER_PROJECT} files")
    existing_size = sum(path.stat().st_size for path in existing_files)

    safe_name = sanitize_filename(file.filename)
    validate_upload_type(safe_name, file.content_type)
    dest = resolve_upload_path(upload_dir, safe_name)
    if dest.exists():
        raise HTTPException(status_code=409, detail="A file with this name is already attached")

    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit")
                if existing_size + total > MAX_PROJECT_SIZE:
                    raise HTTPException(status_code=413, detail="Project upload storage limit exceeded")
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return {
        "name": safe_name,
        "size": total,
        "type": file.content_type or "text/plain",
        "path": f"uploads/{safe_name}",
    }


@router.get("")
def list_uploads(project_id: str, current_user: UserResponse = Depends(get_current_user)):
    project = project_service.get_project(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    upload_dir = settings.projects_dir / project_id / "uploads"
    if not upload_dir.exists():
        return []

    results = []
    for f in upload_dir.iterdir():
        if f.is_file():
            results.append({
                "name": f.name,
                "size": f.stat().st_size,
                "path": f"uploads/{f.name}",
            })
    return results
