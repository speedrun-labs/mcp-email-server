import pytest


def test_list_accounts(service):
    accounts = service.list_accounts()
    assert len(accounts) >= 1
    assert accounts[0]["name"] == "default"


def test_parse_recipients_json(service):
    data = '[{"to": "a@b.com", "name": "Alice"}, {"to": "c@d.com", "name": "Bob"}]'
    result = service._parse_recipients(data)
    assert len(result) == 2
    assert result[0]["to"] == "a@b.com"
    assert result[0]["name"] == "Alice"


def test_parse_recipients_csv(service):
    data = "to,name,id\na@b.com,Alice,1\nc@d.com,Bob,2"
    result = service._parse_recipients(data)
    assert len(result) == 2
    assert result[0]["to"] == "a@b.com"
    assert result[1]["name"] == "Bob"


async def test_send_email_validates_recipients(service):
    with pytest.raises(ValueError, match="At least one recipient"):
        await service.send_email(to="", subject="Test", body="Test")


async def test_send_email_validates_domains(service):
    """When allowed_domains is set, recipients outside are rejected."""
    import os
    os.environ["APP_ALLOWED_DOMAINS"] = "example.com"
    try:
        from mcp_mail.config import Settings
        from mcp_mail.accounts import AccountRegistry
        from mcp_mail.services.email_service import EmailService

        s = Settings()
        r = AccountRegistry(s)
        svc = EmailService(r, s)
        with pytest.raises(ValueError, match="not in the allowed"):
            await svc.send_email(to="user@evil.com", subject="Test", body="Test")
    finally:
        del os.environ["APP_ALLOWED_DOMAINS"]
