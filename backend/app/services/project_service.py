import json
import uuid
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from app.database import db_connection
from app.config import settings
from app.crew.stacks import normalize_stack
from app.models import BuildTokenUsage, ProjectCreate, ProjectResponse
from app.services import template_service

MAX_INLINE_FILE_SIZE = 1024 * 1024  # 1MB

# Internal Neutron metadata — never show these as generated project files.
_HIDDEN_PROJECT_FILES = frozenset({"connectors.json"})
_HIDDEN_PROJECT_DIRS = frozenset({".neutron", "__pycache__", ".git"})


def _is_workspace_visible_file(relative_path: str) -> bool:
    """Return False for Neutron-internal metadata paths (not user-facing artifacts)."""
    # Do not use str.lstrip("./") — that strips individual chars and would
    # turn ".neutron/..." into "neutron/..." (hiding would fail).
    rel = relative_path.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    if rel.startswith("/"):
        rel = rel[1:]
    if not rel:
        return False
    parts = rel.split("/")
    if any(part in _HIDDEN_PROJECT_DIRS for part in parts):
        return False
    if parts[-1] in _HIDDEN_PROJECT_FILES:
        return False
    return True


def _project_from_row(row) -> ProjectResponse:
    data = dict(row)
    usage = BuildTokenUsage(
        total_tokens=data.pop("total_tokens", 0),
        prompt_tokens=data.pop("prompt_tokens", 0),
        completion_tokens=data.pop("completion_tokens", 0),
        successful_requests=data.pop("successful_requests", 0),
    )
    budget = data.pop("token_budget", 0)
    stack = normalize_stack(data.pop("stack", None))
    return ProjectResponse(
        **data,
        stack=stack,
        token_usage=usage,
        token_budget=budget,
        token_budget_percent=round(usage.total_tokens / budget * 100, 1) if budget > 0 else None,
    )


def create_project(data: ProjectCreate, owner_user_id: str | None = None) -> ProjectResponse:
    project_id = str(uuid.uuid4())
    project_dir = settings.projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # Stack: explicit request > template default > static.
    stack = "static"
    if data.template:
        tmpl = template_service.get_template(data.template)
        if tmpl:
            stack = normalize_stack(tmpl.get("stack"))
    if data.stack is not None:
        stack = normalize_stack(data.stack)

    with db_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, template, stack, owner_user_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, data.name, data.description, data.template, stack, owner_user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row)


def list_projects(owner_user_id: str | None = None) -> list[ProjectResponse]:
    with db_connection() as conn:
        if owner_user_id:
            rows = conn.execute("SELECT * FROM projects WHERE owner_user_id = ? ORDER BY created_at DESC", (owner_user_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [_project_from_row(r) for r in rows]


def get_project(project_id: str, owner_user_id: str | None = None) -> ProjectResponse | None:
    with db_connection() as conn:
        if owner_user_id:
            row = conn.execute("SELECT * FROM projects WHERE id = ? AND owner_user_id = ?", (project_id, owner_user_id)).fetchone()
        else:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        return None
    return _project_from_row(row)


def get_project_owner_user_id(project_id: str) -> str | None:
    with db_connection() as conn:
        row = conn.execute("SELECT owner_user_id FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row["owner_user_id"] if row else None


def delete_project(project_id: str, owner_user_id: str | None = None) -> bool:
    with db_connection() as conn:
        if owner_user_id:
            result = conn.execute("DELETE FROM projects WHERE id = ? AND owner_user_id = ?", (project_id, owner_user_id))
        else:
            result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        deleted = result.rowcount > 0
    if deleted:
        project_dir = settings.projects_dir / project_id
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
    return deleted


def get_project_status(project_id: str) -> str | None:
    with db_connection() as conn:
        row = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row["status"] if row else None


def update_project_status(project_id: str, status: str):
    with db_connection() as conn:
        conn.execute(
            "UPDATE projects SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, project_id),
        )
        conn.commit()


def update_project_token_usage(
    project_id: str,
    *,
    total_tokens: int,
    prompt_tokens: int,
    completion_tokens: int,
    successful_requests: int,
    token_budget: int,
) -> None:
    """Persist cumulative build usage so reconnects and reloads retain it."""
    with db_connection() as conn:
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            return
        conn.execute(
            """
            UPDATE projects
            SET total_tokens = ?, prompt_tokens = ?, completion_tokens = ?,
                successful_requests = ?, token_budget = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                max(0, total_tokens),
                max(0, prompt_tokens),
                max(0, completion_tokens),
                max(0, successful_requests),
                max(0, token_budget),
                project_id,
            ),
        )
        conn.commit()


def get_project_files(project_id: str) -> list[dict]:
    project_dir = settings.projects_dir / project_id
    if not project_dir.exists():
        return []
    files = []
    for f in project_dir.rglob("*"):
        if f.is_file() and not f.is_symlink():
            rel = f.relative_to(project_dir).as_posix()
            if not _is_workspace_visible_file(rel):
                continue
            if f.stat().st_size > MAX_INLINE_FILE_SIZE:
                content = "[file too large to display]"
            else:
                try:
                    content = f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = "[binary file]"
            files.append({"file_path": rel, "content": content})
    return files


def save_message(
    project_id: str,
    role: str,
    content: str,
    agent: str | None = None,
    *,
    kind: str | None = None,
    metadata: dict | None = None,
):
    metadata_json = None
    if metadata is not None:
        try:
            metadata_json = json.dumps(metadata, default=str)
        except (TypeError, ValueError):
            metadata_json = None

    with db_connection() as conn:
        conn.execute(
            "INSERT INTO messages (project_id, role, agent, content, kind, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, role, agent, content, kind, metadata_json),
        )
        conn.commit()


def get_messages(project_id: str) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        ).fetchall()
    messages: list[dict] = []
    for row in rows:
        item = dict(row)
        raw_meta = item.get("metadata")
        if isinstance(raw_meta, str) and raw_meta.strip():
            try:
                item["metadata"] = json.loads(raw_meta)
            except (TypeError, json.JSONDecodeError):
                item["metadata"] = None
        else:
            item["metadata"] = None
        messages.append(item)
    return messages


def build_project_zip(project_id: str) -> BytesIO:
    project_dir = settings.projects_dir / project_id
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        if project_dir.exists():
            for path in project_dir.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    rel = path.relative_to(project_dir).as_posix()
                    if not _is_workspace_visible_file(rel):
                        continue
                    archive.write(path, rel)
    buffer.seek(0)
    return buffer
