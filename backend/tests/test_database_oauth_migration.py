import sqlite3

from app.database import init_db


def test_init_db_adds_oauth_tokens_column_to_existing_provider_settings(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE user_provider_settings (
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            base_url TEXT,
            api_key_encrypted TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, provider)
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("app.database.DB_PATH", db_path)
    init_db()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(user_provider_settings)").fetchall()}
    conn.close()
    assert "oauth_tokens_encrypted" in columns