from datetime import datetime, timedelta, timezone

from app.auth.security import SESSION_COOKIE_NAME, hash_password, hash_session_token, verify_password
from app.database import db_connection
from app.models import UserCreate
from app.services import auth_service


def test_register_sets_session_cookie_and_me_returns_user(client):
    response = client.post(
        "/api/auth/register",
        json={"email": " User@Example.COM ", "password": "password123", "display_name": " User "},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["display_name"] == "User"
    assert "session_token" not in data
    assert SESSION_COOKIE_NAME in response.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == data["id"]


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dupe@example.com", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already registered."


def test_login_rejects_invalid_credentials(client):
    auth_service.create_user(UserCreate(email="user@example.com", password="password123"))

    response = client.post("/api/auth/login", json={"email": "user@example.com", "password": "wrongpass"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_sets_session_and_logout_revokes_it(client):
    user = auth_service.create_user(UserCreate(email="user@example.com", password="password123"))

    login = client.post("/api/auth/login", json={"email": " USER@example.com ", "password": "password123"})

    assert login.status_code == 200
    login_data = login.json()
    assert login_data["id"] == user.id
    assert "session_token" not in login_data
    raw_token = login.cookies[SESSION_COOKIE_NAME]

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 200
    assert logout.json() == {"ok": True}
    with db_connection() as conn:
        row = conn.execute("SELECT revoked_at FROM sessions WHERE token_hash = ?", (hash_session_token(raw_token),)).fetchone()
    assert row["revoked_at"] is not None
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_cookie_is_ok(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required."


def test_expired_session_is_ignored(client):
    user = auth_service.create_user(UserCreate(email="old@example.com", password="password123"))
    raw_token, _ = auth_service.create_session(user.id)
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    with db_connection() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?", (expired, hash_session_token(raw_token)))
        conn.commit()

    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    assert client.get("/api/auth/me").status_code == 401


def test_me_accepts_bearer_token(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "bearer@example.com", "password": "password123"},
    )
    token, _ = auth_service.create_session(response.json()["id"])
    client.cookies.clear()

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == "bearer@example.com"


def test_logout_revokes_bearer_session(client):
    register = client.post(
        "/api/auth/register",
        json={"email": "bearer-logout@example.com", "password": "password123"},
    )
    token, _ = auth_service.create_session(register.json()["id"])
    client.cookies.clear()

    logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert logout.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_password_verify_rejects_bad_hashes():
    password_hash = hash_password("password123")

    assert verify_password("password123", password_hash) is True
    assert verify_password("wrongpass", password_hash) is False
    assert verify_password("password123", "argon2$1$salt$digest") is False
    assert verify_password("password123", "argon2$bad") is False
    assert verify_password("password123", None) is False  # type: ignore[arg-type]


def test_login_rate_limited_after_too_many_attempts(client):
    from app.auth.rate_limit import MAX_ATTEMPTS

    for _ in range(MAX_ATTEMPTS):
        client.post("/api/auth/login", json={"email": "x@y.com", "password": "wrong"})

    response = client.post("/api/auth/login", json={"email": "x@y.com", "password": "wrong"})
    assert response.status_code == 429


def test_register_rate_limited_after_too_many_attempts(client):
    from app.auth.rate_limit import MAX_ATTEMPTS

    for i in range(MAX_ATTEMPTS):
        client.post("/api/auth/register", json={"email": f"user{i}@rate.com", "password": "password123"})

    response = client.post("/api/auth/register", json={"email": "final@rate.com", "password": "password123"})
    assert response.status_code == 429
