"""
FastAPI application entrypoint.

Wires: structured logging, CORS, global exception handlers (graceful
degradation for LLM/vector-DB/MCP/tool failures per spec), and the
auth + chat routers.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes_admin import router as admin_router
from backend.app.api.routes_auth import router as auth_router
from backend.app.api.routes_chat import router as chat_router
from backend.app.api.routes_tools import router as tools_router
from backend.app.config import get_settings
from backend.app.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("main")

app = FastAPI(title="Enterprise AI Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # POC only — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(tools_router)
app.include_router(admin_router)



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Last-resort handler so an unexpected failure anywhere (LLM outage,
    vector DB down, MCP unreachable) degrades to a clean 500 JSON payload
    instead of leaking a stack trace to the client."""
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. The team has been notified via logs."},
    )
