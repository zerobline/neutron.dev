import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Ensure CrewAI agents do not require a paid API key during test collection/imports.
os.environ.setdefault("LLM_MODEL", "ollama/llama3.1")

from app.config import settings  # noqa: E402

settings.llm_model = "ollama/llama3.1"

# Use a single temp directory for the static files mount (set at import time in main.py)
# but reset it before every test so tests remain isolated.
_TEST_PROJECTS_DIR = Path(tempfile.mkdtemp(prefix="atoms_test_projects_"))
settings.projects_dir = _TEST_PROJECTS_DIR
settings.projects_dir.mkdir(parents=True, exist_ok=True)


def _cleanup_projects_dir():
    shutil.rmtree(_TEST_PROJECTS_DIR, ignore_errors=True)


atexit.register(_cleanup_projects_dir)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.auth.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def clean_projects_dir():
    """Reset shared filesystem and LLM settings before each test."""
    settings.llm_provider = None
    settings.llm_model = "ollama/llama3.1"
    settings.openai_api_key = None
    settings.openai_base_url = None
    settings.moonshot_api_key = None
    settings.moonshot_base_url = "https://api.moonshot.ai/v1"
    if _TEST_PROJECTS_DIR.exists():
        shutil.rmtree(_TEST_PROJECTS_DIR)
    _TEST_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    settings.llm_provider = None
    settings.llm_model = "ollama/llama3.1"
    settings.openai_api_key = None
    settings.openai_base_url = None
    settings.moonshot_api_key = None
    settings.moonshot_base_url = "https://api.moonshot.ai/v1"


@pytest.fixture
def settings_projects_dir():
    """Expose the shared temporary projects directory to tests."""
    yield _TEST_PROJECTS_DIR


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Provide a fresh SQLite database file for a test."""
    db_path = tmp_path / "atoms.db"
    monkeypatch.setattr("app.database.DB_PATH", db_path)
    from app.database import init_db

    init_db()
    yield db_path


@pytest.fixture
def client(temp_db):
    """FastAPI TestClient with a fresh DB and clean projects directory."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
