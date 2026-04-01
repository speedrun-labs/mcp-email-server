import json
import os

import pytest


def test_default_account_loaded(settings):
    assert "default" in settings.accounts
    acct = settings.accounts["default"]
    assert acct.smtp.host == "localhost"
    assert acct.smtp.port == 1025
    assert acct.smtp.from_address == "test@example.com"
    assert acct.imap.host == "localhost"


def test_accounts_json():
    os.environ["ACCOUNTS_JSON"] = json.dumps({
        "work": {
            "smtp": {"host": "smtp.work.com", "port": 587, "from_address": "me@work.com"},
            "imap": {"host": "imap.work.com", "port": 993},
            "from_address": "me@work.com",
            "rate_limit_per_minute": 10,
            "allowed_domains": ["work.com"],
        }
    })
    try:
        from mcp_mail.config import Settings
        s = Settings()
        assert "work" in s.accounts
        assert s.accounts["work"].smtp.host == "smtp.work.com"
        assert s.accounts["work"].from_address == "me@work.com"
        assert s.accounts["work"].rate_limit_per_minute == 10
        assert s.accounts["work"].allowed_domains == ["work.com"]
    finally:
        del os.environ["ACCOUNTS_JSON"]


def test_app_settings_defaults(settings):
    assert settings.app.rate_limit_per_minute == 30
    assert settings.app.max_recipients == 50
    assert settings.app.max_body_length == 20000


def test_auth_mode_none(settings):
    assert settings.auth.mode == "none"
