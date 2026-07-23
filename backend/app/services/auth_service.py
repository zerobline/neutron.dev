import uuid
from sqlite3 import IntegrityError

from app.auth.security import create_session_token, hash_password, hash_session_token, session_expires_at, verify_password
from app.config import settings
from app.database import db_connection
from app.models import UserCreate, UserResponse


class AuthError(Exception):
    pass


class DuplicateUserError(AuthError):
    pass


def _user_response(row) -> UserResponse:
    return UserResponse(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        created_at=row["created_at"],
    )


def create_user(data: UserCreate) -> UserResponse:
    user_id = str(uuid.uuid4())
    with db_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
                (user_id, data.email, hash_password(data.password), data.display_name),
            )
            # Derive the user's initial active provider + model from global .env/settings at registration time.
            # This ensures new authenticated users respect LLM_PROVIDER/LLM_MODEL instead of always openai.
            # A skeleton provider row is seeded (model only; no key material is copied from .env).
            default_provider = settings.infer_provider()
            default_model = settings.default_model_for_provider(default_provider)
            default_base_url = settings.default_base_url_for_provider(default_provider)
            conn.execute(
                "INSERT INTO user_settings (user_id, active_provider) VALUES (?, ?)",
                (user_id, default_provider),
            )
            conn.execute(
                """
                INSERT INTO user_provider_settings (user_id, provider, model, base_url, api_key_encrypted)
                VALUES (?, ?, ?, ?, NULL)
                ON CONFLICT(user_id, provider) DO NOTHING
                """,
                (user_id, default_provider, default_model, default_base_url),
            )
            conn.commit()
        except IntegrityError as exc:
            raise DuplicateUserError("Email is already registered.") from exc
        row = conn.execute("SELECT id, email, display_name, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_response(row)


def authenticate_user(email: str, password: str) -> UserResponse | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return _user_response(row)


def create_session(user_id: str) -> tuple[str, str]:
    token = create_session_token()
    expires_at = session_expires_at(settings.auth_session_days)
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, token.token_hash, expires_at),
        )
        conn.commit()
    return token.raw, expires_at


def get_user_by_session(raw_token: str | None) -> UserResponse | None:
    if not raw_token:
        return None
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.email, users.display_name, users.created_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
              AND sessions.revoked_at IS NULL
              AND datetime(sessions.expires_at) > datetime('now')
            """,
            (hash_session_token(raw_token),),
        ).fetchone()
    return _user_response(row) if row else None


def revoke_session(raw_token: str | None) -> None:
    if not raw_token:
        return
    with db_connection() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at = datetime('now') WHERE token_hash = ?",
            (hash_session_token(raw_token),),
        )
        conn.commit()
