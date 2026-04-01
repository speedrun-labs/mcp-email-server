from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

from mcp_mail.accounts import AccountContext, AccountRegistry
from mcp_mail.config import Settings
from mcp_mail.services import imap_client, smtp_client
from mcp_mail.validators import (
    check_allowed_domains,
    check_max_recipients,
    render_template,
    sanitize_subject,
    validate_email_address,
    validate_email_list,
)

logger = logging.getLogger(__name__)


class EmailService:
    """Core email operations. All tools and API routes delegate here."""

    def __init__(self, registry: AccountRegistry, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings

    def _effective_max_recipients(self, ctx: AccountContext) -> int:
        return ctx.max_recipients or self.settings.app.max_recipients

    def _effective_allowed_domains(self, ctx: AccountContext) -> list[str]:
        if ctx.allowed_domains is not None:
            return ctx.allowed_domains
        return self.settings.app.allowed_domains_list

    # --- Account ---

    def list_accounts(self) -> list[dict]:
        return self.registry.list_all()

    # --- Send ---

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        account: str | None = None,
        html_body: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        reply_to: str | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
        reply_all: bool = False,
        attachments: list[dict] | None = None,
    ) -> dict:
        ctx = self.registry.get(account)
        ctx.rate_limiter.check()

        to_list = validate_email_list(to)
        cc_list = validate_email_list(cc or "")
        bcc_list = validate_email_list(bcc or "")

        if not to_list:
            raise ValueError("At least one recipient is required")

        # Validate body length on send side too
        max_len = self.settings.app.max_body_length
        if len(body) > max_len:
            raise ValueError(f"Body length ({len(body)}) exceeds maximum ({max_len})")
        if html_body and len(html_body) > max_len:
            raise ValueError(f"HTML body length ({len(html_body)}) exceeds maximum ({max_len})")

        max_recip = self._effective_max_recipients(ctx)
        check_max_recipients(to_list, cc_list, bcc_list, max_recip)

        allowed = self._effective_allowed_domains(ctx)
        all_recipients = to_list + cc_list + bcc_list
        check_allowed_domains(all_recipients, allowed)

        subject = sanitize_subject(subject)

        # reply_all: agent must provide the original recipients in to/cc.
        # We just ensure threading headers are set.
        # The tool description guides the agent to include original recipients.

        message = smtp_client.build_message(
            from_address=ctx.config.effective_from_address,
            from_name=ctx.config.effective_from_name,
            to=to_list,
            subject=subject,
            body=body,
            html_body=html_body,
            cc=cc_list or None,
            bcc=bcc_list or None,
            reply_to=reply_to,
            in_reply_to=in_reply_to,
            references=references,
            attachments=attachments,
        )

        message_id = await smtp_client.send_email(ctx.config.smtp, message, bcc=bcc_list)

        # Save to Sent folder
        if ctx.config.save_to_sent:
            await imap_client.append_to_sent(ctx.config.imap, message)

        return {"status": "sent", "message_id": message_id}

    async def send_bulk(
        self,
        subject_template: str,
        body_template: str,
        recipients: str,
        account: str | None = None,
        html_body_template: str | None = None,
    ) -> dict:
        ctx = self.registry.get(account)

        # Parse recipients (auto-detect JSON vs CSV)
        recipient_list = self._parse_recipients(recipients)
        if not recipient_list:
            raise ValueError("No recipients provided")

        max_recip = self._effective_max_recipients(ctx)
        if len(recipient_list) > max_recip:
            raise ValueError(f"Total recipients ({len(recipient_list)}) exceeds max ({max_recip})")

        # Validate ALL emails and templates before sending any
        allowed = self._effective_allowed_domains(ctx)
        for i, r in enumerate(recipient_list):
            if "to" not in r:
                raise ValueError(f"Recipient at index {i} is missing 'to' field")
            validate_email_address(r["to"])
        if allowed:
            check_allowed_domains([r["to"] for r in recipient_list], allowed)

        # Pre-validate templates with first recipient's variables to catch errors early
        if recipient_list:
            first_vars = {k: v for k, v in recipient_list[0].items() if k != "to"}
            render_template(subject_template, first_vars)
            render_template(body_template, first_vars)
            if html_body_template:
                render_template(html_body_template, first_vars)

        results = []
        sent = 0
        failed = 0

        for r in recipient_list:
            to_addr = r["to"]
            variables = {k: v for k, v in r.items() if k != "to"}
            try:
                ctx.rate_limiter.check()
                subj = render_template(subject_template, variables)
                bod = render_template(body_template, variables)
                html_bod = render_template(html_body_template, variables) if html_body_template else None

                message = smtp_client.build_message(
                    from_address=ctx.config.effective_from_address,
                    from_name=ctx.config.effective_from_name,
                    to=[to_addr],
                    subject=sanitize_subject(subj),
                    body=bod,
                    html_body=html_bod,
                )
                msg_id = await smtp_client.send_email(ctx.config.smtp, message)
                results.append({"to": to_addr, "status": "sent", "message_id": msg_id})
                sent += 1
            except Exception as e:
                logger.warning("Bulk send failed for %s: %s", to_addr, e)
                results.append({"to": to_addr, "status": "failed", "error": str(e)})
                failed += 1

        return {"total": len(recipient_list), "sent": sent, "failed": failed, "results": results}

    def _parse_recipients(self, data: str) -> list[dict[str, str]]:
        """Auto-detect JSON array or CSV string."""
        data = data.strip()
        if not data:
            raise ValueError("Recipients data is empty")
        if data.startswith("["):
            try:
                parsed = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON recipients: {e}")
            if not isinstance(parsed, list):
                raise ValueError("Recipients JSON must be an array")
            return parsed
        # Try CSV
        try:
            reader = csv.DictReader(io.StringIO(data))
            return [dict(row) for row in reader]
        except csv.Error as e:
            raise ValueError(f"Invalid CSV recipients: {e}")

    async def test_connection(self, account: str | None = None) -> dict:
        """Test connectivity. Returns consistent format regardless of single/all."""
        if account:
            ctx = self.registry.get(account)
            smtp_result = await smtp_client.test_smtp_connection(ctx.config.smtp)
            imap_result = await imap_client.test_imap_connection(ctx.config.imap)
            return {"accounts": {ctx.name: {"smtp": smtp_result, "imap": imap_result}}}
        # Test all accounts
        results = {}
        for info in self.registry.list_all():
            name = info["name"]
            try:
                ctx = self.registry.get(name)
                smtp_r = await smtp_client.test_smtp_connection(ctx.config.smtp)
                imap_r = await imap_client.test_imap_connection(ctx.config.imap)
                results[name] = {"smtp": smtp_r, "imap": imap_r}
            except Exception as e:
                results[name] = {"error": str(e)}
        return {"accounts": results}

    # --- Read ---

    async def list_emails(
        self,
        account: str | None = None,
        mailbox: str = "INBOX",
        limit: int = 20,
        offset: int = 0,
        sender: str | None = None,
        subject: str | None = None,
        since: str | None = None,
        before: str | None = None,
        body_contains: str | None = None,
        flags: str | None = None,
    ) -> dict:
        ctx = self.registry.get(account)
        return await imap_client.list_emails(
            settings=ctx.config.imap,
            mailbox=mailbox,
            limit=limit,
            offset=offset,
            sender=sender,
            subject=subject,
            since=since,
            before=before,
            body_contains=body_contains,
            flags=flags,
        )

    async def get_emails(
        self,
        ids: str,
        account: str | None = None,
        mailbox: str = "INBOX",
    ) -> list[dict]:
        ctx = self.registry.get(account)
        uids = [uid.strip() for uid in ids.split(",") if uid.strip()]
        if not uids:
            raise ValueError("At least one email ID is required")
        return await imap_client.get_emails(
            settings=ctx.config.imap,
            uids=uids,
            mailbox=mailbox,
            max_body_length=self.settings.app.max_body_length,
        )

    async def list_folders(self, account: str | None = None) -> list[dict]:
        ctx = self.registry.get(account)
        return await imap_client.list_folders(ctx.config.imap)

    # --- Manage ---

    async def move_emails(
        self,
        ids: str,
        to_mailbox: str,
        account: str | None = None,
        from_mailbox: str = "INBOX",
    ) -> dict:
        ctx = self.registry.get(account)
        uids = [uid.strip() for uid in ids.split(",") if uid.strip()]
        return await imap_client.move_emails(ctx.config.imap, uids, from_mailbox, to_mailbox)

    async def mark_emails(
        self,
        ids: str,
        action: str,
        account: str | None = None,
        mailbox: str = "INBOX",
    ) -> dict:
        ctx = self.registry.get(account)
        uids = [uid.strip() for uid in ids.split(",") if uid.strip()]
        return await imap_client.mark_emails(ctx.config.imap, uids, mailbox, action)

    async def delete_emails(
        self,
        ids: str,
        account: str | None = None,
        mailbox: str = "INBOX",
    ) -> dict:
        ctx = self.registry.get(account)
        uids = [uid.strip() for uid in ids.split(",") if uid.strip()]
        return await imap_client.delete_emails(ctx.config.imap, uids, mailbox)
