import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DB_PATH = Path(os.environ["DATABASE_PATH"]) if "DATABASE_PATH" in os.environ else Path(__file__).resolve().parent.parent / "neutron.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def check_db() -> None:
    with db_connection() as conn:
        conn.execute("SELECT 1").fetchone()


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute("PRAGMA table_info(\"{}\")".format(table.replace("\"", '""'))).fetchall()
    return any(row["name"] == column for row in rows)


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                template TEXT,
                stack TEXT NOT NULL DEFAULT 'static',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                agent TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(project_id, file_path)
            );
            CREATE TABLE IF NOT EXISTS user_provider_settings (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                base_url TEXT,
                api_key_encrypted TEXT,
                oauth_tokens_encrypted TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, provider)
            );
            CREATE TABLE IF NOT EXISTS user_search_provider_settings (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                api_key_encrypted TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, provider)
            );
            CREATE TABLE IF NOT EXISTS user_mcp_connector_settings (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                connector_key TEXT NOT NULL,
                api_key_encrypted TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, connector_key)
            );
            CREATE TABLE IF NOT EXISTS oauth_device_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                device_code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                interval_seconds INTEGER NOT NULL DEFAULT 5,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                active_provider TEXT NOT NULL DEFAULT 'openai',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_search_provider_settings_user_id ON user_search_provider_settings(user_id);
            CREATE INDEX IF NOT EXISTS idx_mcp_connector_settings_user_id ON user_mcp_connector_settings(user_id);
        """)
        if not _column_exists(conn, "projects", "owner_user_id"):
            conn.execute("ALTER TABLE projects ADD COLUMN owner_user_id TEXT REFERENCES users(id) ON DELETE CASCADE")
        project_usage_columns = {
            "total_tokens": "INTEGER NOT NULL DEFAULT 0",
            "prompt_tokens": "INTEGER NOT NULL DEFAULT 0",
            "completion_tokens": "INTEGER NOT NULL DEFAULT 0",
            "successful_requests": "INTEGER NOT NULL DEFAULT 0",
            "token_budget": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in project_usage_columns.items():
            if not _column_exists(conn, "projects", column):
                conn.execute(f"ALTER TABLE projects ADD COLUMN {column} {definition}")
        if not _column_exists(conn, "user_provider_settings", "oauth_tokens_encrypted"):
            conn.execute("ALTER TABLE user_provider_settings ADD COLUMN oauth_tokens_encrypted TEXT")
        # Structured chat cards (phase_result) need kind + metadata so refresh
        # rehydrates PhaseResultCard UI instead of plain agent bubbles.
        if not _column_exists(conn, "messages", "kind"):
            conn.execute("ALTER TABLE messages ADD COLUMN kind TEXT")
        if not _column_exists(conn, "messages", "metadata"):
            conn.execute("ALTER TABLE messages ADD COLUMN metadata TEXT")
        if not _column_exists(conn, "user_settings", "agent_models"):
            conn.execute("ALTER TABLE user_settings ADD COLUMN agent_models TEXT")
        if not _column_exists(conn, "projects", "stack"):
            conn.execute("ALTER TABLE projects ADD COLUMN stack TEXT NOT NULL DEFAULT 'static'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner_user_id ON projects(owner_user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_oauth_device_sessions_user_id ON oauth_device_sessions(user_id)")
        conn.commit()
