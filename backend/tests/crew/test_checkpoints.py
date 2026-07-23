import sqlite3

from app.crew.checkpoints import (
    build_checkpoint_config,
    checkpoint_available,
    checkpoint_db_path,
    latest_checkpoint,
    list_checkpoints,
)


def test_build_checkpoint_config_uses_project_db(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    config = build_checkpoint_config("proj-1", restore_from="db#abc")
    assert config.restore_from == "db#abc"
    assert str(checkpoint_db_path("proj-1")) in config.location


def test_list_and_latest_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    db_path = checkpoint_db_path("proj-1")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE checkpoints (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                parent_id TEXT,
                branch TEXT NOT NULL DEFAULT 'main',
                data JSON NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO checkpoints (id, created_at, parent_id, branch, data) VALUES (?, ?, ?, ?, ?)",
            ("older", "2026-01-01T00:00:00Z", None, "main", "{}"),
        )
        conn.execute(
            "INSERT INTO checkpoints (id, created_at, parent_id, branch, data) VALUES (?, ?, ?, ?, ?)",
            ("newer", "2026-01-02T00:00:00Z", "older", "main", "{}"),
        )
        conn.commit()

    checkpoints = list_checkpoints("proj-1")
    assert len(checkpoints) == 2
    assert checkpoints[0]["id"] == "newer"
    assert latest_checkpoint("proj-1") == f"{db_path}#newer"
    assert checkpoint_available("proj-1") is True


def test_checkpoint_available_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.crew.checkpoints.settings.projects_dir", tmp_path)
    assert checkpoint_available("missing") is False
    assert latest_checkpoint("missing") is None