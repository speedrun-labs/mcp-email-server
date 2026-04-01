from __future__ import annotations

import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

import aiosmtplib

from mcp_mail.config import SmtpSettings


def build_message(
    from_address: str,
    from_name: str | None,
    to: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    attachments: list[dict] | None = None,
) -> EmailMessage:
    """Build a MIME email message."""
    msg = EmailMessage()

    # Headers
    if from_name:
        msg["From"] = formataddr((from_name, from_address))
    else:
        msg["From"] = from_address
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_address.rsplit("@", 1)[-1])

    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Body
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    # Attachments
    if attachments:
        import base64
        import mimetypes

        MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB

        for att in attachments:
            filename = att.get("filename", "attachment")
            content_b64 = att.get("content", "")
            if not content_b64:
                continue
            content_type = att.get("content_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            if "/" not in content_type:
                content_type = "application/octet-stream"

            try:
                data = base64.b64decode(content_b64)
            except Exception:
                raise ValueError(f"Invalid base64 content for attachment '{filename}'")

            if len(data) > MAX_ATTACHMENT_SIZE:
                raise ValueError(f"Attachment '{filename}' exceeds max size (25 MB)")

            maintype, subtype = content_type.split("/", 1)
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    return msg


async def send_email(
    smtp_settings: SmtpSettings,
    message: EmailMessage,
    bcc: list[str] | None = None,
) -> str:
    """Send an email via SMTP. Returns the Message-ID."""
    tls_context = None
    if not smtp_settings.verify_ssl:
        tls_context = ssl.create_default_context()
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE

    recipients = []
    if message["To"]:
        recipients.extend([a.strip() for a in message["To"].split(",")])
    if message["Cc"]:
        recipients.extend([a.strip() for a in message["Cc"].split(",")])
    if bcc:
        recipients.extend(bcc)

    kwargs: dict = {
        "hostname": smtp_settings.host,
        "port": smtp_settings.port,
        "username": smtp_settings.username,
        "timeout": 30,
    }
    if smtp_settings.password:
        kwargs["password"] = smtp_settings.password.get_secret_value()
    if smtp_settings.use_tls:
        kwargs["use_tls"] = True
        if tls_context:
            kwargs["tls_context"] = tls_context
    elif smtp_settings.start_tls:
        kwargs["start_tls"] = True
        if tls_context:
            kwargs["tls_context"] = tls_context

    await aiosmtplib.send(
        message,
        recipients=recipients,
        **kwargs,
    )

    return message["Message-ID"]


async def test_smtp_connection(smtp_settings: SmtpSettings) -> dict:
    """Test SMTP connectivity. Returns server info."""
    tls_context = None
    if not smtp_settings.verify_ssl:
        tls_context = ssl.create_default_context()
        tls_context.check_hostname = False
        tls_context.verify_mode = ssl.CERT_NONE

    kwargs: dict = {
        "hostname": smtp_settings.host,
        "port": smtp_settings.port,
        "timeout": 10,
    }
    if smtp_settings.use_tls:
        kwargs["use_tls"] = True
        if tls_context:
            kwargs["tls_context"] = tls_context
    elif smtp_settings.start_tls:
        kwargs["start_tls"] = True
        if tls_context:
            kwargs["tls_context"] = tls_context

    if smtp_settings.username:
        kwargs["username"] = smtp_settings.username
    if smtp_settings.password:
        kwargs["password"] = smtp_settings.password.get_secret_value()

    smtp = aiosmtplib.SMTP(**kwargs)
    try:
        await smtp.connect()
        return {"status": "connected", "host": smtp_settings.host, "port": smtp_settings.port}
    finally:
        try:
            await smtp.quit()
        except Exception:
            pass
