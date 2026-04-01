from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mcp_mail.services.email_service import EmailService

# Tools are registered via register_tools(mcp, service) called from server.py


def register_tools(mcp, service: EmailService) -> None:
    """Register all MCP tools on the FastMCP server instance."""

    # --- Account ---

    @mcp.tool(
        name="mail_list_accounts",
        description=(
            "List all configured email accounts. Returns account name, from_address, "
            "smtp_host, and imap_host for each account. Passwords are never included. "
            "Call this first to discover which accounts are available."
        ),
    )
    async def mail_list_accounts() -> list[dict]:
        return service.list_accounts()

    # --- Send ---

    @mcp.tool(
        name="mail_send",
        description=(
            "Send an email via SMTP. Required: to, subject, body. "
            "To reply to an email: set in_reply_to to the original Message-ID (from mail_get response) "
            "and references to the original References header. "
            "To reply-all: also set reply_all=true and include all original recipients in to/cc. "
            "Returns {status, message_id} on success."
        ),
    )
    async def mail_send(
        to: Annotated[str, Field(description="Comma-separated recipient email addresses")],
        subject: Annotated[str, Field(description="Email subject line")],
        body: Annotated[str, Field(description="Plain text email body")],
        account: Annotated[str | None, Field(description="Account name (default if omitted)")] = None,
        html_body: Annotated[str | None, Field(description="HTML email body")] = None,
        cc: Annotated[str | None, Field(description="Comma-separated CC addresses")] = None,
        bcc: Annotated[str | None, Field(description="Comma-separated BCC addresses")] = None,
        reply_to: Annotated[str | None, Field(description="Reply-To address")] = None,
        in_reply_to: Annotated[str | None, Field(description="Message-ID for reply threading")] = None,
        references: Annotated[str | None, Field(description="References header for threading")] = None,
        reply_all: Annotated[bool, Field(description="Auto-populate recipients from original when replying")] = False,
    ) -> dict:
        return await service.send_email(
            to=to, subject=subject, body=body, account=account,
            html_body=html_body, cc=cc, bcc=bcc, reply_to=reply_to,
            in_reply_to=in_reply_to, references=references, reply_all=reply_all,
        )

    @mcp.tool(
        name="mail_send_bulk",
        description=(
            "Mail merge: send personalized emails to multiple recipients using templates. "
            "Place {{variable}} placeholders in subject_template and body_template. "
            "Pass recipients as either: "
            '(1) JSON array: [{"to":"a@b.com","name":"Alice"}, ...] or '
            '(2) CSV string: "to,name\\na@b.com,Alice\\n..." '
            "The 'to' field is required. All other fields become template variables. "
            "Returns {total, sent, failed, results} with per-recipient status."
        ),
    )
    async def mail_send_bulk(
        subject_template: Annotated[str, Field(description="Subject with {{variable}} placeholders")],
        body_template: Annotated[str, Field(description="Body with {{variable}} placeholders")],
        recipients: Annotated[str, Field(description="JSON array or CSV string with 'to' field + variables")],
        account: Annotated[str | None, Field(description="Account name")] = None,
        html_body_template: Annotated[str | None, Field(description="HTML body template")] = None,
    ) -> dict:
        return await service.send_bulk(
            subject_template=subject_template, body_template=body_template,
            recipients=recipients, account=account, html_body_template=html_body_template,
        )

    @mcp.tool(
        name="mail_test_connection",
        description="Test SMTP/IMAP connectivity for one or all accounts.",
    )
    async def mail_test_connection(
        account: Annotated[str | None, Field(description="Account name (tests all if omitted)")] = None,
    ) -> dict:
        return await service.test_connection(account)

    # --- Read ---

    @mcp.tool(
        name="mail_list",
        description=(
            "List email metadata (headers only — no body content). "
            "Returns: {emails: [{uid, from, to, subject, date, flags, has_attachments}, ...], total_count, has_more}. "
            "Use the uid values with mail_get to fetch full content. "
            "Supports filters: sender, subject, body_contains, since/before (DD-Mon-YYYY format), "
            "flags (SEEN, UNSEEN, FLAGGED, ANSWERED). "
            "Paginate with limit/offset. Results are sorted newest-first."
        ),
    )
    async def mail_list(
        account: Annotated[str | None, Field(description="Account name")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name")] = "INBOX",
        limit: Annotated[int, Field(description="Max results per page", le=100)] = 20,
        offset: Annotated[int, Field(description="Skip first N results", ge=0)] = 0,
        sender: Annotated[str | None, Field(description="Filter by sender address")] = None,
        subject: Annotated[str | None, Field(description="Filter by subject keyword")] = None,
        since: Annotated[str | None, Field(description="Filter emails since date (DD-Mon-YYYY)")] = None,
        before: Annotated[str | None, Field(description="Filter emails before date (DD-Mon-YYYY)")] = None,
        body_contains: Annotated[str | None, Field(description="Filter by body text content")] = None,
        flags: Annotated[str | None, Field(description="Comma-separated flags: SEEN,UNSEEN,FLAGGED,ANSWERED")] = None,
    ) -> dict:
        return await service.list_emails(
            account=account, mailbox=mailbox, limit=limit, offset=offset,
            sender=sender, subject=subject, since=since, before=before,
            body_contains=body_contains, flags=flags,
        )

    @mcp.tool(
        name="mail_get",
        description=(
            "Get full email content by UID(s) from mail_list. Pass comma-separated UIDs for batch fetch. "
            "Returns: [{uid, from, to, subject, date, message_id, in_reply_to, references, "
            "text_body, html_body, attachments: [{filename, content_type, size}]}]. "
            "Use message_id and references when replying with mail_send."
        ),
    )
    async def mail_get(
        ids: Annotated[str, Field(description="Comma-separated email UIDs")],
        account: Annotated[str | None, Field(description="Account name")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name")] = "INBOX",
    ) -> list[dict]:
        return await service.get_emails(ids=ids, account=account, mailbox=mailbox)

    @mcp.tool(
        name="mail_list_folders",
        description="List all IMAP folders/mailboxes with unread counts.",
    )
    async def mail_list_folders(
        account: Annotated[str | None, Field(description="Account name")] = None,
    ) -> list[dict]:
        return await service.list_folders(account)

    # --- Manage ---

    @mcp.tool(
        name="mail_move",
        description=(
            "Move emails between folders by UIDs. Common uses: "
            "move to 'Trash' to soft-delete, move to 'Archive' to archive. "
            "Use mail_list_folders to discover available folder names."
        ),
    )
    async def mail_move(
        ids: Annotated[str, Field(description="Comma-separated email UIDs")],
        to_mailbox: Annotated[str, Field(description="Destination folder name")],
        account: Annotated[str | None, Field(description="Account name")] = None,
        from_mailbox: Annotated[str, Field(description="Source folder name")] = "INBOX",
    ) -> dict:
        return await service.move_emails(ids=ids, to_mailbox=to_mailbox, account=account, from_mailbox=from_mailbox)

    @mcp.tool(
        name="mail_mark",
        description="Mark emails as read/unread/flagged/unflagged. Batch by comma-separated UIDs.",
    )
    async def mail_mark(
        ids: Annotated[str, Field(description="Comma-separated email UIDs")],
        action: Annotated[str, Field(description="Action: read | unread | flagged | unflagged")],
        account: Annotated[str | None, Field(description="Account name")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name")] = "INBOX",
    ) -> dict:
        return await service.mark_emails(ids=ids, action=action, account=account, mailbox=mailbox)

    @mcp.tool(
        name="mail_delete",
        description="Permanently delete emails by UIDs.",
    )
    async def mail_delete(
        ids: Annotated[str, Field(description="Comma-separated email UIDs")],
        account: Annotated[str | None, Field(description="Account name")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name")] = "INBOX",
    ) -> dict:
        return await service.delete_emails(ids=ids, account=account, mailbox=mailbox)
