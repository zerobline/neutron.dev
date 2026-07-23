from fastapi import Request, WebSocket

from app.auth.security import SESSION_COOKIE_NAME

BEARER_PREFIX = "bearer "


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith(BEARER_PREFIX):
        token = authorization[len(BEARER_PREFIX) :].strip()
        return token or None
    return None


def extract_session_token(request: Request) -> str | None:
    token = extract_bearer_token(request.headers.get("Authorization"))
    if token:
        return token
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    return cookie if isinstance(cookie, str) and cookie else None


def extract_websocket_session_token(ws: WebSocket) -> str | None:
    query_token = ws.query_params.get("token")
    if isinstance(query_token, str) and query_token:
        return query_token
    cookie = ws.cookies.get(SESSION_COOKIE_NAME)
    return cookie if isinstance(cookie, str) and cookie else None