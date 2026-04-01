import pytest

from mcp_mail.accounts import AccountContext, AccountRegistry, RateLimiter


def test_rate_limiter_allows():
    rl = RateLimiter(max_per_minute=10)
    for _ in range(10):
        rl.check()  # Should not raise


def test_rate_limiter_rejects():
    rl = RateLimiter(max_per_minute=1)
    rl.check()  # First one OK
    with pytest.raises(ValueError, match="Rate limit exceeded"):
        rl.check()  # Second should fail


def test_account_registry_get_default(registry):
    ctx = registry.get()
    assert ctx.name == "default"
    assert ctx.config.smtp.host == "localhost"


def test_account_registry_get_missing(registry):
    with pytest.raises(ValueError, match="'nonexistent' not found"):
        registry.get("nonexistent")


def test_account_masked_info(registry):
    ctx = registry.get()
    info = ctx.masked_info()
    assert info["name"] == "default"
    assert info["from_address"] == "test@example.com"
    assert "password" not in str(info)


def test_list_all(registry):
    accounts = registry.list_all()
    assert len(accounts) >= 1
    assert accounts[0]["name"] == "default"
