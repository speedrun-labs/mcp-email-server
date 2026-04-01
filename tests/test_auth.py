import os

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def bearer_app():
    os.environ["AUTH_MODE"] = "bearer"
    os.environ["AUTH_BEARER_TOKEN"] = "test-secret-token"
    try:
        from mcp_mail.app import create_app
        from mcp_mail.config import Settings
        return create_app(Settings())
    finally:
        os.environ["AUTH_MODE"] = "none"
        del os.environ["AUTH_BEARER_TOKEN"]


@pytest.fixture
async def bearer_client(bearer_app):
    transport = ASGITransport(app=bearer_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_no_auth_required(bearer_client):
    """Health endpoint works without auth even in bearer mode."""
    resp = await bearer_client.get("/api/v1/mail/health")
    assert resp.status_code != 401


async def test_accounts_requires_auth(bearer_client):
    """List accounts returns 401 without bearer token."""
    resp = await bearer_client.get("/api/v1/accounts")
    assert resp.status_code == 401


async def test_accounts_valid_token(bearer_client):
    """List accounts works with valid bearer token."""
    resp = await bearer_client.get(
        "/api/v1/accounts",
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert resp.status_code == 200


async def test_accounts_invalid_token(bearer_client):
    """List accounts returns 401 with wrong token."""
    resp = await bearer_client.get(
        "/api/v1/accounts",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


async def test_send_requires_auth(bearer_client):
    """Send endpoint returns 401 without token."""
    resp = await bearer_client.post("/api/v1/mail/send", json={
        "to": "test@example.com",
        "subject": "Test",
        "body": "Test",
    })
    assert resp.status_code == 401
