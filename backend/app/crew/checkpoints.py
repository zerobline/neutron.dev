import logging
import sqlite3
from pathlib import Path

from crewai import CheckpointConfig
from crewai.state.provider.sqlite_provider import SqliteProvider

from app.config import settings

logger = logging.getLogger(__name__)

CHECKPOINT_SUBDIR = ".checkpoints"
CHECKPOINT_DB_NAME = "flow.db"
DEFAULT_MAX_CHECKPOINTS = 20

# Only fire when a crew/method is *done* — never mid-stream/tool mutation.
# (model_dump during concurrent state edits caused pyo3 panics previously.)
SAFE_CHECKPOINT_EVENTS = [
    "crew_kickoff_completed",
    "crew_kickoff_failed",
    "method_execution_finished",
    "method_execution_failed",
    "flow_paused",
]


def checkpoint_db_path(project_id: str) -> Path:
    return settings.projects_dir / project_id / CHECKPOINT_SUBDIR / CHECKPOINT_DB_NAME


def build_checkpoint_config(
    project_id: str,
    *,
    restore_from: str | Path | None = None,
) -> CheckpointConfig:
    db_path = checkpoint_db_path(project_id)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception("Could not create checkpoint directory for %s", project_id)
    return CheckpointConfig(
        location=str(db_path),
        # Safe events only. File writes use PrivateAttr during crews and are
        # synced onto state at post-crew quiescent points before dumps matter.
        on_events=list(SAFE_CHECKPOINT_EVENTS),
        provider=SqliteProvider(),
        max_checkpoints=DEFAULT_MAX_CHECKPOINTS,
        restore_from=restore_from,
    )


def _checkpoint_db_exists(project_id: str) -> bool:
    return checkpoint_db_path(project_id).exists()


def list_checkpoints(project_id: str, *, branch: str = "main") -> list[dict[str, str]]:
    db_path = checkpoint_db_path(project_id)
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, parent_id, branch
            FROM checkpoints
            WHERE branch = ?
            ORDER BY rowid DESC
            """,
            (branch,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "created_at": row[1],
            "parent_id": row[2] or "",
            "branch": row[3],
            "location": f"{db_path}#{row[0]}",
        }
        for row in rows
    ]


def latest_checkpoint(project_id: str, *, branch: str = "main") -> str | None:
    checkpoints = list_checkpoints(project_id, branch=branch)
    if not checkpoints:
        return None
    return checkpoints[0]["location"]


def checkpoint_available(project_id: str) -> bool:
    return _checkpoint_db_exists(project_id) and latest_checkpoint(project_id) is not None