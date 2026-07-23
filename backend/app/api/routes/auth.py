from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import get_current_user
from app.auth.rate_limit import check_rate_limit
from app.auth.session import extract_session_token
from app.config import session_cookie_samesite, settings
from app.auth.security import SESSION_COOKIE_NAME
from app.models import AuthResponse, UserCreate, UserLogin, UserResponse
from app.services import auth_service
from app.services.auth_service import DuplicateUserError

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _session_cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": session_cookie_samesite(),
        "max_age": settings.auth_session_days * 24 * 60 * 60,
        "path": "/",
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE_NAME, token, **_session_cookie_kwargs())


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        samesite=session_cookie_samesite(),
    )


def _auth_response(user: UserResponse) -> AuthResponse:
    return AuthResponse(**user.model_dump())


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_rate_limit)])
def register(data: UserCreate, response: Response):
    try:
        user = auth_service.create_user(data)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token, _ = auth_service.create_session(user.id)
    _set_session_cookie(response, token)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(check_rate_limit)])
def login(data: UserLogin, response: Response):
    user = auth_service.authenticate_user(data.email, data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    token, _ = auth_service.create_session(user.id)
    _set_session_cookie(response, token)
    return _auth_response(user)


@router.post("/logout")
def logout(request: Request, response: Response):
    auth_service.revoke_session(extract_session_token(request))
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def me(current_user: UserResponse = Depends(get_current_user)):
    return current_user
