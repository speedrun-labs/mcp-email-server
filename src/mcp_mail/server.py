from __future__ import annotations

from fastmcp import FastMCP

from mcp_mail.accounts import AccountRegistry
from mcp_mail.config import Settings
from mcp_mail.services.email_service import EmailService
from mcp_mail.tools import register_tools


def create_mcp_server(settings: Settings, registry: AccountRegistry) -> FastMCP:
    """Create and configure the FastMCP server with all tools."""
    service = EmailService(registry, settings)

    mcp = FastMCP(
        name="mcp-mail",
        instructions="""\
Email server for sending and reading emails via SMTP/IMAP. Supports multiple accounts.

## Getting Started
1. Call `mail_list_accounts` to see available accounts and their from addresses.
2. All tools accept an optional `account` parameter. Omit it to use the default account.

## Reading Emails
- `mail_list` returns **metadata only** (from, to, subject, date, flags, uid). Use filters to narrow results.
- `mail_get` returns **full content** (text body, HTML body, attachments). Pass the `uid` values from `mail_list`.
- `mail_list_folders` shows all folders with unread counts.
- Workflow: `mail_list(flags="UNSEEN")` → pick UIDs → `mail_get(ids="uid1,uid2")` → read content.

## Sending Emails
- `mail_send` sends a single email. Required: `to`, `subject`, `body`.
- To reply: pass `in_reply_to` (the original Message-ID from `mail_get`) and `references`.
- To reply-all: also set `reply_all=true` and include all original recipients in `to`/`cc`.
- `mail_send_bulk` sends personalized emails using `{{variable}}` templates. Pass recipients as JSON array or CSV.

## Managing Emails
- `mail_move` moves emails between folders (e.g., move to Trash, Archive).
- `mail_mark` marks emails as read/unread/flagged/unflagged.
- `mail_delete` permanently deletes emails (cannot be undone).

## Date Format
For `since` and `before` filters in `mail_list`, use IMAP date format: `DD-Mon-YYYY` (e.g., `01-Jan-2026`).
""",
    )

    register_tools(mcp, service)
    return mcp
