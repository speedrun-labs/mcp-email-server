from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mcp_mail.config import AuthSettings

_security = HTTPBearer(auto_error=False)


def create_bearer_dependency(auth_settings: AuthSettings):
    """Create a FastAPI dependency for bearer token verification."""

    async def verify_bearer(
        creds: HTTPAuthorizationCredentials | None = Security(_security),
    ) -> str | None:
        if auth_settings.mode == "none":
            return None
        if not creds:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        if auth_settings.mode == "bearer":
            if not auth_settings.bearer_token:
                raise HTTPException(status_code=500, detail="Bearer token not configured on server")
            if creds.credentials != auth_settings.bearer_token.get_secret_value():
                raise HTTPException(status_code=401, detail="Invalid bearer token")
            return creds.credentials
        raise HTTPException(status_code=500, detail=f"Unknown auth mode: {auth_settings.mode}")

    return verify_bearer


def create_optional_bearer_dependency(auth_settings: AuthSettings):
    """Create a dependency that doesn't require auth (for health endpoints)."""

    async def no_auth() -> None:
        return None

    return no_auth
