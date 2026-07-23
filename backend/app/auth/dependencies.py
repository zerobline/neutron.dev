from fastapi import HTTPException, Request, WebSocket, status

from app.auth.session import extract_session_token, extract_websocket_session_token
from app.models import UserResponse
from app.services import auth_service


def get_current_user(request: Request) -> UserResponse:
    user = auth_service.get_user_by_session(extract_session_token(request))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def get_optional_user(request: Request) -> UserResponse | None:
    return auth_service.get_user_by_session(extract_session_token(request))


def get_websocket_user(ws: WebSocket) -> UserResponse | None:
    return auth_service.get_user_by_session(extract_websocket_session_token(ws))
