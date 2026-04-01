from __future__ import annotations

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    to: str = Field(description="Comma-separated recipient email addresses")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Plain text body")
    account: str | None = Field(default=None, description="Account name (default if omitted)")
    html_body: str | None = Field(default=None, description="HTML body")
    cc: str | None = Field(default=None, description="Comma-separated CC addresses")
    bcc: str | None = Field(default=None, description="Comma-separated BCC addresses")
    reply_to: str | None = Field(default=None, description="Reply-To address")
    in_reply_to: str | None = Field(default=None, description="Message-ID for reply threading")
    references: str | None = Field(default=None, description="References header for threading")
    reply_all: bool = Field(default=False, description="Auto-populate recipients from original email")
    attachments: list[dict] | None = Field(default=None, description="Attachments as base64")


class SendBulkRequest(BaseModel):
    subject_template: str = Field(description="Subject with {{variable}} placeholders")
    body_template: str = Field(description="Body with {{variable}} placeholders")
    recipients: str = Field(description="JSON array or CSV string with 'to' field + variables")
    account: str | None = Field(default=None, description="Account name")
    html_body_template: str | None = Field(default=None, description="HTML body template")


class ListRequest(BaseModel):
    account: str | None = None
    mailbox: str = "INBOX"
    limit: int = 20
    offset: int = 0
    sender: str | None = None
    subject: str | None = None
    since: str | None = None
    before: str | None = None
    body_contains: str | None = None
    flags: str | None = None


class MoveRequest(BaseModel):
    ids: str = Field(description="Comma-separated email UIDs")
    to_mailbox: str = Field(description="Destination folder")
    account: str | None = None
    from_mailbox: str = "INBOX"


class MarkRequest(BaseModel):
    ids: str = Field(description="Comma-separated email UIDs")
    action: str = Field(description="read | unread | flagged | unflagged")
    account: str | None = None
    mailbox: str = "INBOX"


class DeleteRequest(BaseModel):
    ids: str = Field(description="Comma-separated email UIDs")
    account: str | None = None
    mailbox: str = "INBOX"
