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
            "List all configured email accounts. Call this FIRST before using any other mail tool "
            "to discover which accounts are available.\n\n"
            "Returns a list of accounts, each with:\n"
            "- name: account identifier to pass as the 'account' parameter in other tools\n"
            "- from_address: the email address this account sends from\n"
            "- from_name: display name for outgoing emails\n"
            "- smtp_host: SMTP server hostname\n"
            "- imap_host: IMAP server hostname\n\n"
            "Passwords and credentials are never included in the response.\n\n"
            "Example response:\n"
            '[{"name": "default", "from_address": "me@gmail.com", "smtp_host": "smtp.gmail.com", "imap_host": "imap.gmail.com"}]'
        ),
    )
    async def mail_list_accounts() -> list[dict]:
        return service.list_accounts()

    # --- Send ---

    @mcp.tool(
        name="mail_send",
        description=(
            "Send an email via SMTP. The email is sent immediately and cannot be undone.\n\n"
            "REQUIRED parameters: to, subject, body\n"
            "OPTIONAL: account, html_body, cc, bcc, reply_to, in_reply_to, references, reply_all\n\n"
            "HOW TO SEND A NEW EMAIL:\n"
            '  mail_send(to="bob@example.com", subject="Hello", body="Hi Bob, ...")\n\n'
            "HOW TO REPLY TO AN EMAIL:\n"
            "  1. First use mail_get to read the original email\n"
            "  2. From the response, get the message_id and references fields\n"
            "  3. Call mail_send with:\n"
            '     - to: the original sender\'s address (from the "from" field)\n'
            "     - subject: original subject (add 'Re: ' prefix if not already present)\n"
            "     - in_reply_to: the original email's message_id\n"
            "     - references: the original email's references + message_id\n\n"
            "HOW TO REPLY-ALL:\n"
            "  Same as reply, but also include all original recipients:\n"
            '  - to: original sender\n'
            '  - cc: all original to/cc recipients (excluding yourself)\n'
            "  - reply_all: true\n\n"
            "HOW TO SEND HTML EMAIL:\n"
            "  Set both body (plain text fallback) and html_body (HTML version).\n"
            "  Recipients with HTML-capable clients see html_body, others see body.\n\n"
            "Returns: {status: 'sent', message_id: '<unique-id@domain>'}\n"
            "The message_id can be used as in_reply_to for threading."
        ),
    )
    async def mail_send(
        to: Annotated[str, Field(description="Comma-separated recipient email addresses. Example: 'alice@example.com' or 'alice@example.com, bob@example.com'")],
        subject: Annotated[str, Field(description="Email subject line. For replies, prefix with 'Re: ' if not already present")],
        body: Annotated[str, Field(description="Plain text email body. Always required, used as fallback when html_body is provided")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit to use the default account")] = None,
        html_body: Annotated[str | None, Field(description="HTML email body. If provided, body becomes the plain text fallback")] = None,
        cc: Annotated[str | None, Field(description="Comma-separated CC addresses. Recipients can see CC but not BCC")] = None,
        bcc: Annotated[str | None, Field(description="Comma-separated BCC addresses. Hidden from all other recipients")] = None,
        reply_to: Annotated[str | None, Field(description="Reply-To address. If set, replies go to this address instead of the sender")] = None,
        in_reply_to: Annotated[str | None, Field(description="Message-ID of the email being replied to. Get this from mail_get response's message_id field")] = None,
        references: Annotated[str | None, Field(description="Space-separated Message-IDs for email threading. Get from mail_get response's references field, append the message_id")] = None,
        reply_all: Annotated[bool, Field(description="Set to true when replying to all recipients. You must manually include original recipients in to/cc")] = False,
    ) -> dict:
        return await service.send_email(
            to=to, subject=subject, body=body, account=account,
            html_body=html_body, cc=cc, bcc=bcc, reply_to=reply_to,
            in_reply_to=in_reply_to, references=references, reply_all=reply_all,
        )

    @mcp.tool(
        name="mail_send_bulk",
        description=(
            "Mail merge: send personalized emails to multiple recipients using templates.\n\n"
            "Use {{variable}} placeholders in subject_template and body_template. "
            "Each recipient gets a unique email with their variables substituted.\n\n"
            "RECIPIENTS FORMAT — provide as JSON array or CSV string:\n\n"
            "JSON example:\n"
            '  [{"to": "alice@example.com", "name": "Alice", "company": "Acme"},\n'
            '   {"to": "bob@example.com", "name": "Bob", "company": "Corp"}]\n\n'
            "CSV example:\n"
            '  "to,name,company\\nalice@example.com,Alice,Acme\\nbob@example.com,Bob,Corp"\n\n'
            "Rules:\n"
            "- The 'to' field is REQUIRED in every recipient\n"
            "- All other fields become template variables\n"
            "- All emails are validated BEFORE sending starts\n"
            "- Each email is sent individually (not BCC'd) for proper personalization\n"
            "- Rate limited per account settings\n\n"
            "TEMPLATE example:\n"
            '  subject_template: "Hello {{name}}, update from {{company}}"\n'
            '  body_template: "Dear {{name}},\\n\\nYour account at {{company}} has been updated."\n\n'
            "Returns: {total: 2, sent: 2, failed: 0, results: [{to, status, message_id}, ...]}\n"
            "Check the results array for per-recipient status — some may fail while others succeed."
        ),
    )
    async def mail_send_bulk(
        subject_template: Annotated[str, Field(description="Subject line with {{variable}} placeholders. Example: 'Hello {{name}}, your order {{order_id}} is ready'")],
        body_template: Annotated[str, Field(description="Body text with {{variable}} placeholders. Example: 'Dear {{name}},\\n\\nYour order {{order_id}} has shipped.'")],
        recipients: Annotated[str, Field(description="JSON array or CSV string. Must have 'to' field. All other fields are template variables. Example: '[{\"to\":\"a@b.com\",\"name\":\"Alice\"}]'")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        html_body_template: Annotated[str | None, Field(description="HTML body with {{variable}} placeholders. If provided, body_template becomes plain text fallback")] = None,
    ) -> dict:
        return await service.send_bulk(
            subject_template=subject_template, body_template=body_template,
            recipients=recipients, account=account, html_body_template=html_body_template,
        )

    @mcp.tool(
        name="mail_test_connection",
        description=(
            "Test SMTP and IMAP connectivity for one or all accounts.\n\n"
            "Use this to verify that email credentials are correct and servers are reachable.\n\n"
            "- Pass account name to test a specific account\n"
            "- Omit account to test ALL configured accounts\n\n"
            "Returns: {accounts: {account_name: {smtp: {status, host, port}, imap: {status, host, port}}}}\n"
            "If a connection fails, the error message is included instead of status."
        ),
    )
    async def mail_test_connection(
        account: Annotated[str | None, Field(description="Account name to test. Omit to test all accounts")] = None,
    ) -> dict:
        return await service.test_connection(account)

    # --- Read ---

    @mcp.tool(
        name="mail_list",
        description=(
            "List email metadata (headers only — no body content). Use this to browse and search emails.\n\n"
            "Returns: {emails: [...], total_count: N, has_more: true/false}\n\n"
            "Each email in the list contains:\n"
            "- uid: unique ID for this email (use with mail_get, mail_move, mail_mark, mail_delete)\n"
            "- from: sender address\n"
            "- to: recipient addresses\n"
            "- subject: email subject\n"
            "- date: date sent\n"
            "- flags: list of IMAP flags (e.g., ['\\Seen', '\\Flagged'])\n"
            "- has_attachments: true if email has file attachments\n"
            "- message_id: unique Message-ID header\n\n"
            "FILTERING:\n"
            "- sender: filter by sender email address\n"
            "- subject: filter by keyword in subject\n"
            "- body_contains: search within email body text\n"
            "- since: only emails after this date (format: DD-Mon-YYYY, e.g., '01-Jan-2026')\n"
            "- before: only emails before this date (same format)\n"
            "- flags: comma-separated flags to filter by: SEEN, UNSEEN, FLAGGED, ANSWERED\n\n"
            "PAGINATION:\n"
            "- Results are sorted newest-first\n"
            "- Default: 20 results per page (max 100)\n"
            "- Use offset to get next page: offset=0 for page 1, offset=20 for page 2, etc.\n"
            "- Check has_more to know if more pages exist\n\n"
            "WORKFLOW:\n"
            "  1. mail_list() → get UIDs from results\n"
            "  2. mail_get(ids='uid1,uid2') → read full content of interesting emails\n\n"
            "EXAMPLES:\n"
            "  Unread emails: mail_list(flags='UNSEEN')\n"
            "  From specific sender: mail_list(sender='boss@company.com')\n"
            "  Last week's emails: mail_list(since='25-Mar-2026')\n"
            "  Search body: mail_list(body_contains='invoice')\n"
            "  Sent folder: mail_list(mailbox='Sent')"
        ),
    )
    async def mail_list(
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name. Default: 'INBOX'. Use mail_list_folders to see all folders")] = "INBOX",
        limit: Annotated[int, Field(description="Max results per page (1-100). Default: 20", le=100)] = 20,
        offset: Annotated[int, Field(description="Number of results to skip for pagination. Default: 0. Use offset=20 for page 2", ge=0)] = 0,
        sender: Annotated[str | None, Field(description="Filter: only emails from this sender address")] = None,
        subject: Annotated[str | None, Field(description="Filter: only emails with this keyword in subject")] = None,
        since: Annotated[str | None, Field(description="Filter: only emails after this date. Format: DD-Mon-YYYY (e.g., '01-Jan-2026')")] = None,
        before: Annotated[str | None, Field(description="Filter: only emails before this date. Format: DD-Mon-YYYY (e.g., '31-Dec-2026')")] = None,
        body_contains: Annotated[str | None, Field(description="Filter: search for this text in email body")] = None,
        flags: Annotated[str | None, Field(description="Filter by flags. Comma-separated: SEEN, UNSEEN, FLAGGED, UNFLAGGED, ANSWERED")] = None,
    ) -> dict:
        return await service.list_emails(
            account=account, mailbox=mailbox, limit=limit, offset=offset,
            sender=sender, subject=subject, since=since, before=before,
            body_contains=body_contains, flags=flags,
        )

    @mcp.tool(
        name="mail_get",
        description=(
            "Get full email content by UID(s). Use UIDs from mail_list results.\n\n"
            "Pass a single UID or comma-separated UIDs for batch fetch.\n\n"
            "Each email in the response contains:\n"
            "- uid: the email UID\n"
            "- from, to, cc, subject, date: header fields\n"
            "- message_id: unique Message-ID (use as in_reply_to when replying with mail_send)\n"
            "- in_reply_to: Message-ID this email is replying to (for thread context)\n"
            "- references: space-separated Message-IDs of the email thread\n"
            "- text_body: plain text content of the email\n"
            "- html_body: HTML content (if available)\n"
            "- attachments: list of {filename, content_type, size} for each attachment\n\n"
            "REPLYING TO AN EMAIL:\n"
            "  After reading an email with mail_get, to reply:\n"
            "  mail_send(\n"
            "    to='original-sender@example.com',\n"
            "    subject='Re: ' + original_subject,\n"
            "    body='Your reply text...',\n"
            "    in_reply_to=email['message_id'],\n"
            "    references=email['references'] + ' ' + email['message_id']\n"
            "  )\n\n"
            "EXAMPLES:\n"
            "  Single email: mail_get(ids='123')\n"
            "  Multiple: mail_get(ids='123,456,789')\n"
            "  From Sent folder: mail_get(ids='123', mailbox='Sent')"
        ),
    )
    async def mail_get(
        ids: Annotated[str, Field(description="Comma-separated email UIDs from mail_list results. Example: '123' or '123,456,789'")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder name where the emails are. Default: 'INBOX'")] = "INBOX",
    ) -> list[dict]:
        return await service.get_emails(ids=ids, account=account, mailbox=mailbox)

    @mcp.tool(
        name="mail_list_folders",
        description=(
            "List all IMAP folders/mailboxes with unread counts.\n\n"
            "Returns a list of folders, each with:\n"
            "- name: folder name (use this as the 'mailbox' parameter in other tools)\n"
            "- unread: number of unread emails in this folder\n\n"
            "Common folders: INBOX, Sent, Drafts, Trash, Spam, Archive.\n"
            "Gmail uses special names like '[Gmail]/Sent Mail', '[Gmail]/All Mail'.\n\n"
            "Use the folder name as the 'mailbox' parameter in mail_list, mail_get, mail_move, etc.\n\n"
            "Example response:\n"
            '[{"name": "INBOX", "unread": 5}, {"name": "Sent", "unread": 0}, {"name": "Trash", "unread": 0}]'
        ),
    )
    async def mail_list_folders(
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
    ) -> list[dict]:
        return await service.list_folders(account)

    # --- Manage ---

    @mcp.tool(
        name="mail_move",
        description=(
            "Move emails between folders by UIDs.\n\n"
            "Common operations:\n"
            "- Archive: mail_move(ids='123', to_mailbox='Archive')\n"
            "- Trash: mail_move(ids='123', to_mailbox='Trash')\n"
            "- Move from Trash back to Inbox: mail_move(ids='123', to_mailbox='INBOX', from_mailbox='Trash')\n\n"
            "Use mail_list_folders to discover available folder names.\n"
            "Supports batch: pass comma-separated UIDs to move multiple emails.\n\n"
            "Returns: {moved: N, from: 'source_folder', to: 'destination_folder'}\n\n"
            "NOTE: This is safer than mail_delete. Use mail_move to Trash instead of permanent deletion."
        ),
    )
    async def mail_move(
        ids: Annotated[str, Field(description="Comma-separated email UIDs to move. Example: '123' or '123,456'")],
        to_mailbox: Annotated[str, Field(description="Destination folder name. Example: 'Trash', 'Archive', 'INBOX'")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        from_mailbox: Annotated[str, Field(description="Source folder where emails currently are. Default: 'INBOX'")] = "INBOX",
    ) -> dict:
        return await service.move_emails(ids=ids, to_mailbox=to_mailbox, account=account, from_mailbox=from_mailbox)

    @mcp.tool(
        name="mail_mark",
        description=(
            "Mark emails as read, unread, flagged, or unflagged. Supports batch operations.\n\n"
            "Actions:\n"
            "- 'read': mark as read (removes unread indicator)\n"
            "- 'unread': mark as unread (shows as new/bold)\n"
            "- 'flagged': add star/flag (important marker)\n"
            "- 'unflagged': remove star/flag\n\n"
            "EXAMPLES:\n"
            "  Mark as read: mail_mark(ids='123', action='read')\n"
            "  Flag important: mail_mark(ids='123,456', action='flagged')\n"
            "  Mark unread: mail_mark(ids='123', action='unread')\n\n"
            "Returns: {marked: N, action: 'read'}"
        ),
    )
    async def mail_mark(
        ids: Annotated[str, Field(description="Comma-separated email UIDs. Example: '123' or '123,456,789'")],
        action: Annotated[str, Field(description="Action to perform. Must be one of: 'read', 'unread', 'flagged', 'unflagged'")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder where the emails are. Default: 'INBOX'")] = "INBOX",
    ) -> dict:
        return await service.mark_emails(ids=ids, action=action, account=account, mailbox=mailbox)

    @mcp.tool(
        name="mail_delete",
        description=(
            "PERMANENTLY delete emails by UIDs. This action CANNOT be undone.\n\n"
            "WARNING: Deleted emails are gone forever. Consider using mail_move to 'Trash' instead.\n\n"
            "EXAMPLES:\n"
            "  Delete one: mail_delete(ids='123')\n"
            "  Delete multiple: mail_delete(ids='123,456,789')\n"
            "  Delete from Trash: mail_delete(ids='123', mailbox='Trash')\n\n"
            "Returns: {deleted: N}\n\n"
            "SAFER ALTERNATIVE: Use mail_move(ids='123', to_mailbox='Trash') to soft-delete."
        ),
    )
    async def mail_delete(
        ids: Annotated[str, Field(description="Comma-separated email UIDs to permanently delete. Example: '123' or '123,456'")],
        account: Annotated[str | None, Field(description="Account name from mail_list_accounts. Omit for default")] = None,
        mailbox: Annotated[str, Field(description="Mailbox/folder where the emails are. Default: 'INBOX'")] = "INBOX",
    ) -> dict:
        return await service.delete_emails(ids=ids, account=account, mailbox=mailbox)
