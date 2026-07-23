"""Snapshot project files for undo and compute simple per-file diffs after edits."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from app.config import settings

_MAX_FILE_BYTES = 400_000
_SKIP_DIRS = {".neutron", "uploads", "__pycache__", "node_modules", ".git"}


def _project_root(project_id: str) -> Path:
    return settings.projects_dir / project_id


def _history_dir(project_id: str) -> Path:
    return _project_root(project_id) / ".neutron"


def _snapshot_path(project_id: str) -> Path:
    return _history_dir(project_id) / "last_edit.json"


def _iter_project_files(project_id: str) -> list[Path]:
    root = _project_root(project_id)
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if path.stat().st_size > _MAX_FILE_BYTES:
            continue
        files.append(path)
    return files


def read_project_texts(project_id: str) -> dict[str, str]:
    root = _project_root(project_id)
    out: dict[str, str] = {}
    for path in _iter_project_files(project_id):
        rel = path.relative_to(root).as_posix()
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return out


def snapshot_before_edit(project_id: str, request: str = "") -> dict[str, str]:
    """Capture current files so the next iterate can be undone."""
    before = read_project_texts(project_id)
    payload = {
        "request": request,
        "before": before,
        "after": None,
        "files_changed": [],
    }
    hist = _history_dir(project_id)
    hist.mkdir(parents=True, exist_ok=True)
    _snapshot_path(project_id).write_text(json.dumps(payload), encoding="utf-8")
    return before


def finalize_edit_snapshot(project_id: str, files_changed: list[str] | None = None) -> dict[str, Any]:
    """After an edit, store after-state and return a diff payload for the UI."""
    path = _snapshot_path(project_id)
    if not path.is_file():
        before: dict[str, str] = {}
        request = ""
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            data = {}
        before = data.get("before") if isinstance(data.get("before"), dict) else {}
        request = str(data.get("request") or "")

    after = read_project_texts(project_id)
    changed = sorted(files_changed or _changed_paths(before, after))
    payload = {
        "request": request,
        "before": before,
        "after": after,
        "files_changed": changed,
    }
    hist = _history_dir(project_id)
    hist.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "can_undo": bool(before) or bool(changed),
        "files_changed": changed,
        "diffs": build_file_diffs(before, after, changed),
        "request": request,
    }


def load_last_edit(project_id: str) -> dict[str, Any] | None:
    path = _snapshot_path(project_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    before = data.get("before") if isinstance(data.get("before"), dict) else {}
    after = data.get("after") if isinstance(data.get("after"), dict) else {}
    changed = data.get("files_changed") if isinstance(data.get("files_changed"), list) else []
    if not changed:
        changed = _changed_paths(before, after or {})
    return {
        "can_undo": bool(before),
        "files_changed": list(changed),
        "diffs": build_file_diffs(before, after or {}, list(changed)),
        "request": str(data.get("request") or ""),
    }


def undo_last_edit(project_id: str) -> dict[str, Any]:
    """Restore the last pre-edit snapshot. Returns restored file list."""
    path = _snapshot_path(project_id)
    if not path.is_file():
        raise FileNotFoundError("No edit to undo.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise FileNotFoundError("No edit to undo.") from exc
    before = data.get("before") if isinstance(data.get("before"), dict) else None
    if not before:
        raise FileNotFoundError("No edit snapshot available.")

    root = _project_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []

    # Restore snapshot files
    for rel, content in before.items():
        if not isinstance(rel, str) or not isinstance(content, str):
            continue
        target = root / rel
        try:
            target.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        restored.append(rel)

    # Remove files created after the snapshot
    after = data.get("after") if isinstance(data.get("after"), dict) else {}
    for rel in after:
        if rel in before:
            continue
        if not isinstance(rel, str):
            continue
        target = root / rel
        try:
            target.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        if target.is_file():
            target.unlink()
            restored.append(rel)

    # Clear snapshot so undo isn't double-applied
    try:
        path.unlink()
    except OSError:
        pass

    return {"restored": sorted(set(restored)), "message": "Last edit undone."}


def _changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


def build_file_diffs(
    before: dict[str, str],
    after: dict[str, str],
    files: list[str] | None = None,
    *,
    max_lines: int = 80,
) -> list[dict[str, Any]]:
    paths = files if files is not None else _changed_paths(before, after)
    diffs: list[dict[str, Any]] = []
    for rel in paths:
        old = before.get(rel, "")
        new = after.get(rel, "")
        if old == new:
            continue
        if rel not in before:
            status = "added"
        elif rel not in after:
            status = "removed"
        else:
            status = "modified"
        unified = list(
            difflib.unified_diff(
                old.splitlines(),
                new.splitlines(),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                lineterm="",
                n=2,
            )
        )
        truncated = len(unified) > max_lines
        if truncated:
            unified = unified[:max_lines]
        diffs.append(
            {
                "path": rel,
                "status": status,
                "diff": "\n".join(unified),
                "truncated": truncated,
            }
        )
    return diffs
