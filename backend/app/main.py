import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import cors_allowed_origins, settings, validate_production_settings
from app.database import check_db, init_db


class _HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return '"GET /api/health ' not in msg


logging.getLogger("uvicorn.access").addFilter(_HealthCheckFilter())
from app.api.routes.projects import router as projects_router
from app.api.routes.templates import router as templates_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.settings import router as settings_router
from app.api.routes.connectors import router as connectors_router
from app.api.routes.skills import router as skills_router
from app.api.routes.auth import router as auth_router
from app.api.routes.oauth import router as oauth_router
from app.api.websockets.project_ws import manager, router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings()
    init_db()
    try:
        # Repair mangled ReAct tool JSON (arrays / spaced keys) before agents run.
        from app.crew.tool_input_repair import install_tool_input_repair

        install_tool_input_repair()
    except Exception:
        logging.getLogger("uvicorn.error").exception("Failed to install tool input repair")
    try:
        yield
    finally:
        await manager.cancel_all_flows()
        try:
            from app.services.project_runtime import runtime_manager

            runtime_manager.stop_all()
        except Exception:
            logging.getLogger("uvicorn.error").exception("Failed to stop project runtimes")


app = FastAPI(title="Neutron API", version="0.1.0", lifespan=lifespan)

MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in MUTATING_METHODS:
            origin = request.headers.get("origin")
            if origin and origin not in cors_allowed_origins():
                return Response("Origin not allowed", status_code=403)
        return await call_next(request)


app.add_middleware(OriginCheckMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(projects_router)
app.include_router(templates_router)
app.include_router(uploads_router)
app.include_router(settings_router)
app.include_router(connectors_router)
app.include_router(skills_router)
app.include_router(ws_router)


@app.get("/api/health")
def health():
    try:
        check_db()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "database": "ok"}
