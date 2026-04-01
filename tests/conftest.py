import os

import pytest

# Set test environment before any imports
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"
os.environ["SMTP_FROM_ADDRESS"] = "test@example.com"
os.environ["SMTP_START_TLS"] = "false"
os.environ["SMTP_USE_TLS"] = "false"
os.environ["IMAP_HOST"] = "localhost"
os.environ["IMAP_PORT"] = "1143"
os.environ["IMAP_USE_SSL"] = "false"
os.environ["AUTH_MODE"] = "none"


@pytest.fixture
def settings():
    from mcp_mail.config import Settings
    return Settings()


@pytest.fixture
def registry(settings):
    from mcp_mail.accounts import AccountRegistry
    return AccountRegistry(settings)


@pytest.fixture
def service(registry, settings):
    from mcp_mail.services.email_service import EmailService
    return EmailService(registry, settings)
