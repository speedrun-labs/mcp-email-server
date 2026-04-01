from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mcp_mail.accounts import AccountRegistry
from mcp_mail.api import create_router
from mcp_mail.auth import create_bearer_dependency, create_optional_bearer_dependency
from mcp_mail.config import Settings
from mcp_mail.server import create_mcp_server
from mcp_mail.services.email_service import EmailService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the combined FastAPI + FastMCP ASGI application."""
    if settings is None:
        settings = Settings()

    registry = AccountRegistry(settings)
    service = EmailService(registry, settings)
    mcp = create_mcp_server(settings, registry)

    # Auth dependencies
    verify_bearer = create_bearer_dependency(settings.auth)
    no_auth = create_optional_bearer_dependency(settings.auth)

    # REST API router
    api_router = create_router(service, verify_bearer, no_auth)

    # MCP HTTP app
    mcp_app = mcp.http_app(path="/")

    # Combined app
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title="MCP Mail Server",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError):
        logger.error("Connection error: %s", exc)
        return JSONResponse(status_code=502, content={"detail": "Email server connection failed"})

    @app.exception_handler(Exception)
    async def general_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled error: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(api_router, prefix="/api/v1")
    app.mount("/mcp", mcp_app)

    return app
