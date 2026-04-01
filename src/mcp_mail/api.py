from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from mcp_mail.schemas import (
    DeleteRequest,
    MarkRequest,
    MoveRequest,
    SendBulkRequest,
    SendRequest,
)
from mcp_mail.services.email_service import EmailService


def create_router(service: EmailService, verify_bearer, no_auth) -> APIRouter:
    router = APIRouter()

    # --- Account ---

    @router.get("/accounts", dependencies=[Depends(verify_bearer)])
    async def list_accounts() -> list[dict]:
        return service.list_accounts()

    # --- Send ---

    @router.post("/mail/send", dependencies=[Depends(verify_bearer)])
    async def send_email(req: SendRequest) -> dict:
        return await service.send_email(
            to=req.to,
            subject=req.subject,
            body=req.body,
            account=req.account,
            html_body=req.html_body,
            cc=req.cc,
            bcc=req.bcc,
            reply_to=req.reply_to,
            in_reply_to=req.in_reply_to,
            references=req.references,
            reply_all=req.reply_all,
            attachments=req.attachments,
        )

    @router.post("/mail/send-bulk", dependencies=[Depends(verify_bearer)])
    async def send_bulk(req: SendBulkRequest) -> dict:
        return await service.send_bulk(
            subject_template=req.subject_template,
            body_template=req.body_template,
            recipients=req.recipients,
            account=req.account,
            html_body_template=req.html_body_template,
        )

    @router.get("/mail/health", dependencies=[Depends(no_auth)])
    async def health() -> dict:
        """Lightweight health check for K8s probes. No SMTP/IMAP connection test."""
        return {"status": "ok"}

    @router.get("/mail/test-connection", dependencies=[Depends(verify_bearer)])
    async def test_connection(account: str | None = Query(None)) -> dict:
        """Full SMTP/IMAP connectivity test."""
        return await service.test_connection(account)

    # --- Read ---

    @router.get("/mail/messages", dependencies=[Depends(verify_bearer)])
    async def list_emails(
        account: str | None = Query(None),
        mailbox: str = Query("INBOX"),
        limit: int = Query(20, le=100),
        offset: int = Query(0, ge=0),
        sender: str | None = Query(None),
        subject: str | None = Query(None),
        since: str | None = Query(None),
        before: str | None = Query(None),
        body_contains: str | None = Query(None),
        flags: str | None = Query(None),
    ) -> dict:
        return await service.list_emails(
            account=account,
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

    @router.get("/mail/messages/{ids}", dependencies=[Depends(verify_bearer)])
    async def get_emails(
        ids: str,
        account: str | None = Query(None),
        mailbox: str = Query("INBOX"),
    ) -> list[dict]:
        return await service.get_emails(ids=ids, account=account, mailbox=mailbox)

    @router.get("/mail/folders", dependencies=[Depends(verify_bearer)])
    async def list_folders(account: str | None = Query(None)) -> list[dict]:
        return await service.list_folders(account)

    # --- Manage ---

    @router.post("/mail/messages/move", dependencies=[Depends(verify_bearer)])
    async def move_emails(req: MoveRequest) -> dict:
        return await service.move_emails(
            ids=req.ids, to_mailbox=req.to_mailbox, account=req.account, from_mailbox=req.from_mailbox
        )

    @router.patch("/mail/messages/mark", dependencies=[Depends(verify_bearer)])
    async def mark_emails(req: MarkRequest) -> dict:
        return await service.mark_emails(
            ids=req.ids, action=req.action, account=req.account, mailbox=req.mailbox
        )

    @router.delete("/mail/messages", dependencies=[Depends(verify_bearer)])
    async def delete_emails(req: DeleteRequest) -> dict:
        return await service.delete_emails(ids=req.ids, account=req.account, mailbox=req.mailbox)

    return router
