import pytest
from httpx import ASGITransport, AsyncClient

from mcp_mail.app import create_app
from mcp_mail.config import Settings


@pytest.fixture
def app():
    settings = Settings()
    return create_app(settings)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_no_auth(client):
    """Health endpoint should not return 401."""
    resp = await client.get("/api/v1/mail/health")
    assert resp.status_code != 401


async def test_list_accounts(client):
    """With AUTH_MODE=none, list accounts works without bearer token."""
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "default"
    assert "password" not in str(data)


async def test_send_invalid_email(client):
    """Sending with invalid email returns 422."""
    resp = await client.post("/api/v1/mail/send", json={
        "to": "not-an-email",
        "subject": "Test",
        "body": "Test body",
    })
    assert resp.status_code == 422


async def test_send_empty_to(client):
    """Sending with empty 'to' returns 422."""
    resp = await client.post("/api/v1/mail/send", json={
        "to": "",
        "subject": "Test",
        "body": "Test body",
    })
    assert resp.status_code == 422


async def test_send_bulk_missing_to(client):
    """Bulk send with missing 'to' field returns 422."""
    resp = await client.post("/api/v1/mail/send-bulk", json={
        "subject_template": "Hello {{name}}",
        "body_template": "Dear {{name}}",
        "recipients": '[{"name": "Alice"}]',
    })
    assert resp.status_code == 422
