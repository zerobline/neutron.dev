import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app import database
from app.database import get_db, init_db


def test_db_path_is_patched(temp_db):
    assert database.DB_PATH == temp_db


def test_db_path_from_env(tmp_path):
    custom = tmp_path / "custom.db"
    with patch.dict(os.environ, {"DATABASE_PATH": str(custom)}):
        import importlib
        import app.database as db_mod
        importlib.reload(db_mod)
        assert db_mod.DB_PATH == custom
    importlib.reload(db_mod)


def test_get_db_returns_row_factory_connection(temp_db):
    conn = get_db()
    assert isinstance(conn, sqlite3.Connection)
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_get_db_enables_foreign_keys(temp_db):
    conn = get_db()
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert foreign_keys == 1
    conn.close()


def test_get_db_sets_busy_timeout(temp_db):
    conn = get_db()
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout == 5000
    conn.close()


def test_db_connection_closes_connection(temp_db):
    from app.database import db_connection

    with db_connection() as conn:
        conn.execute("SELECT 1")
    import pytest

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_init_db_enables_wal_mode(temp_db):
    init_db()
    conn = get_db()
    journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode.lower() == "wal"
    conn.close()


def test_init_db_creates_tables(temp_db):
    init_db()  # idempotent
    conn = get_db()
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()
    assert "projects" in tables
    assert "messages" in tables
    assert "project_files" in tables


def test_init_db_creates_expected_columns(temp_db):
    init_db()
    conn = get_db()
    projects_cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
    messages_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    conn.close()
    assert "id" in projects_cols
    assert "name" in projects_cols
    assert "description" in projects_cols
    assert "status" in projects_cols
    assert "template" in projects_cols
    assert "created_at" in projects_cols
    assert "updated_at" in projects_cols
    assert {
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "successful_requests",
        "token_budget",
    }.issubset(projects_cols)
    assert "project_id" in messages_cols
    assert "role" in messages_cols
    assert "agent" in messages_cols
    assert "content" in messages_cols
