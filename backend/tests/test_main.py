import logging
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import _HealthCheckFilter, app


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_endpoint_reports_db_failure(client):
    with patch("app.main.check_db", side_effect=RuntimeError("no db")):
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"


def test_lifespan_calls_init_db():
    with patch("app.main.init_db") as mock_init_db:
        with TestClient(app):
            mock_init_db.assert_called_once()



def test_cors_headers_present(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_origin_check_blocks_unknown_origin_when_secure(client):
    from app.config import settings

    original = settings.cookie_secure
    try:
        settings.cookie_secure = True
        response = client.post(
            "/api/auth/login",
            json={"email": "a@b.com", "password": "x"},
            headers={"Origin": "https://evil.com"},
        )
        assert response.status_code == 403
    finally:
        settings.cookie_secure = original


def test_origin_check_allows_known_origin_when_secure(client):
    from app.config import settings

    original = settings.cookie_secure
    try:
        settings.cookie_secure = True
        response = client.post(
            "/api/auth/login",
            json={"email": "a@b.com", "password": "x"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code != 403
    finally:
        settings.cookie_secure = original


def test_origin_check_blocks_unknown_origin_even_when_not_secure(client):
    from app.config import settings

    original = settings.cookie_secure
    try:
        settings.cookie_secure = False
        response = client.post(
            "/api/auth/login",
            json={"email": "a@b.com", "password": "x"},
            headers={"Origin": "https://evil.com"},
        )
        assert response.status_code == 403
    finally:
        settings.cookie_secure = original


def test_origin_check_allows_get_requests_from_any_origin(client):
    from app.config import settings

    original = settings.cookie_secure
    try:
        settings.cookie_secure = True
        response = client.get(
            "/api/health",
            headers={"Origin": "https://evil.com"},
        )
        assert response.status_code == 200
    finally:
        settings.cookie_secure = original


def test_health_check_filter_suppresses_health_logs():
    f = _HealthCheckFilter()
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '"GET /api/health HTTP/1.1" 200', (), None)
    assert f.filter(record) is False


def test_health_check_filter_passes_other_logs():
    f = _HealthCheckFilter()
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '"POST /api/auth/login HTTP/1.1" 200', (), None)
    assert f.filter(record) is True


def test_origin_check_allows_no_origin_header(client):
    from app.config import settings

    original = settings.cookie_secure
    try:
        settings.cookie_secure = True
        response = client.post(
            "/api/auth/login",
            json={"email": "a@b.com", "password": "x"},
        )
        assert response.status_code != 403
    finally:
        settings.cookie_secure = original
