from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    username: str | None = None
    password: SecretStr | None = None
    use_tls: bool = False
    start_tls: bool = True
    verify_ssl: bool = True
    from_address: str
    from_name: str | None = None
    save_to_sent: bool = True


class ImapSettings(BaseModel):
    host: str
    port: int = 993
    username: str | None = None
    password: SecretStr | None = None
    use_ssl: bool = True
    verify_ssl: bool = True


class AccountConfig(BaseModel):
    smtp: SmtpSettings
    imap: ImapSettings
    from_address: str | None = None
    from_name: str | None = None
    save_to_sent: bool = True
    rate_limit_per_minute: int | None = None
    max_recipients: int | None = None
    allowed_domains: list[str] | None = None

    @property
    def effective_from_address(self) -> str:
        return self.from_address or self.smtp.from_address

    @property
    def effective_from_name(self) -> str | None:
        return self.from_name or self.smtp.from_name


class AuthSettings(BaseModel):
    mode: str = "none"
    bearer_token: SecretStr | None = None


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    rate_limit_per_minute: int = 30
    max_recipients: int = 50
    max_body_length: int = 20000
    allowed_domains: str = ""

    @property
    def allowed_domains_list(self) -> list[str]:
        if not self.allowed_domains:
            return []
        return [d.strip() for d in self.allowed_domains.split(",") if d.strip()]


class SmtpEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMTP_", env_file=".env", extra="ignore")

    host: str = ""
    port: int = 587
    username: str | None = None
    password: SecretStr | None = None
    use_tls: bool = False
    start_tls: bool = True
    verify_ssl: bool = True
    from_address: str = ""
    from_name: str | None = None
    save_to_sent: bool = True


class ImapEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMAP_", env_file=".env", extra="ignore")

    host: str = ""
    port: int = 993
    username: str | None = None
    password: SecretStr | None = None
    use_ssl: bool = True
    verify_ssl: bool = True


class AuthEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    mode: str = "none"
    bearer_token: SecretStr | None = None


class Settings:
    """Loads all settings from environment variables."""

    def __init__(self) -> None:
        self.app = AppSettings()
        auth_env = AuthEnvSettings()
        self.auth = AuthSettings(
            mode=auth_env.mode,
            bearer_token=auth_env.bearer_token,
        )
        self._accounts: dict[str, AccountConfig] = {}
        self._default_name: str = "default"
        self._load_default_account()
        self._load_accounts_json()
        if not self._accounts:
            logger.warning(
                "No email accounts configured. Set SMTP_HOST/IMAP_HOST env vars "
                "or provide ACCOUNTS_JSON."
            )

    def _load_default_account(self) -> None:
        smtp_env = SmtpEnvSettings()
        imap_env = ImapEnvSettings()
        if not smtp_env.host:
            logger.warning("No SMTP_HOST configured, default account will not be available")
            return
        smtp = SmtpSettings(
            host=smtp_env.host,
            port=smtp_env.port,
            username=smtp_env.username,
            password=smtp_env.password,
            use_tls=smtp_env.use_tls,
            start_tls=smtp_env.start_tls,
            verify_ssl=smtp_env.verify_ssl,
            from_address=smtp_env.from_address,
            from_name=smtp_env.from_name,
            save_to_sent=smtp_env.save_to_sent,
        )
        imap = ImapSettings(
            host=imap_env.host,
            port=imap_env.port,
            username=imap_env.username,
            password=imap_env.password,
            use_ssl=imap_env.use_ssl,
            verify_ssl=imap_env.verify_ssl,
        )
        self._accounts[self._default_name] = AccountConfig(smtp=smtp, imap=imap)

    def _load_accounts_json(self) -> None:
        import os

        raw = os.environ.get("ACCOUNTS_JSON", "")
        if not raw:
            return
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Invalid ACCOUNTS_JSON format")
            return
        for name, acct_data in data.items():
            try:
                smtp_data = dict(acct_data.get("smtp", {}))
                imap_data = dict(acct_data.get("imap", {}))
                # Set from_address on smtp if not present
                if "from_address" not in smtp_data:
                    smtp_data["from_address"] = acct_data.get("from_address", "")
                if "from_name" not in smtp_data and acct_data.get("from_name"):
                    smtp_data["from_name"] = acct_data["from_name"]
                smtp = SmtpSettings(**smtp_data)
                imap = ImapSettings(**imap_data)
                account = AccountConfig(
                    smtp=smtp,
                    imap=imap,
                    from_address=acct_data.get("from_address"),
                    from_name=acct_data.get("from_name"),
                    save_to_sent=acct_data.get("save_to_sent", True),
                    rate_limit_per_minute=acct_data.get("rate_limit_per_minute"),
                    max_recipients=acct_data.get("max_recipients"),
                    allowed_domains=acct_data.get("allowed_domains"),
                )
                self._accounts[name] = account
            except Exception:
                logger.error("Failed to load account '%s' from ACCOUNTS_JSON", name, exc_info=True)

    @property
    def accounts(self) -> dict[str, AccountConfig]:
        return self._accounts

    @property
    def default_account_name(self) -> str:
        return self._default_name
