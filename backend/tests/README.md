# Backend Test Suite

This folder contains the full pytest suite for the `backend/app` package.

## Quick start

From the `backend` directory:

```bash
# Activate the virtual environment
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux

# Run the full suite
python -m pytest

# Run with coverage report
python -m pytest --cov=app --cov-report=term-missing

# Run with the enforced 100% coverage gate
python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=100
```

## Layout

- `conftest.py` – shared fixtures: temp SQLite DB, temp projects directory, FastAPI `TestClient`, and CrewAI-safe config.
- `test_main.py` – app boot, health endpoint, CORS, static files.
- `test_config.py` / `test_database.py` / `test_models.py` – config, DB, and pydantic models.
- `api/routes/` – HTTP route integration tests.
- `api/websockets/` – WebSocket connection manager and endpoint tests.
- `services/` – business logic unit tests.
- `crew/` – CrewAI agents, tasks, crews, tools, and the project generation flow (with mocked LLM calls).

## Isolation

- Each test gets a fresh SQLite database file via `temp_db`.
- The projects directory is reset before every test.
- CrewAI/LLM calls are mocked so no API keys are required.
