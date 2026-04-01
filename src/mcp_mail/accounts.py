from __future__ import annotations

import time
import threading

from mcp_mail.config import AccountConfig, Settings


class RateLimiter:
    """Token bucket rate limiter (per-account, in-memory, thread-safe)."""

    def __init__(self, max_per_minute: int) -> None:
        self.max_per_minute = max_per_minute
        self._tokens = float(max_per_minute)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def check(self) -> None:
        """Consume one token. Raises ValueError if rate limit exceeded."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.max_per_minute,
                self._tokens + elapsed * (self.max_per_minute / 60.0),
            )
            self._last_refill = now
            if self._tokens < 1.0:
                raise ValueError(
                    f"Rate limit exceeded: max {self.max_per_minute} sends per minute"
                )
            self._tokens -= 1.0


class AccountContext:
    """Isolated resources for a single email account."""

    def __init__(self, name: str, config: AccountConfig, default_rate_limit: int) -> None:
        self.name = name
        self.config = config
        rate = config.rate_limit_per_minute or default_rate_limit
        self.rate_limiter = RateLimiter(rate)

    @property
    def max_recipients(self) -> int | None:
        return self.config.max_recipients

    @property
    def allowed_domains(self) -> list[str] | None:
        return self.config.allowed_domains

    def masked_info(self) -> dict:
        """Return account info with masked credentials."""
        return {
            "name": self.name,
            "from_address": self.config.effective_from_address,
            "from_name": self.config.effective_from_name,
            "smtp_host": self.config.smtp.host,
            "imap_host": self.config.imap.host,
        }


class AccountRegistry:
    """Manages all AccountContext instances."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._accounts: dict[str, AccountContext] = {}
        self._default = settings.default_account_name
        for name, config in settings.accounts.items():
            self._accounts[name] = AccountContext(
                name=name,
                config=config,
                default_rate_limit=settings.app.rate_limit_per_minute,
            )

    def get(self, name: str | None = None) -> AccountContext:
        """Get account by name, or default if None."""
        key = name or self._default
        if key not in self._accounts:
            raise ValueError(f"Account '{key}' not found")
        return self._accounts[key]

    def list_all(self) -> list[dict]:
        """List all accounts with masked info."""
        return [ctx.masked_info() for ctx in self._accounts.values()]

    @property
    def default_name(self) -> str:
        return self._default
