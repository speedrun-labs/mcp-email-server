from __future__ import annotations

import email
import email.policy
import logging
import re
import ssl
from typing import Any

import aioimaplib

from mcp_mail.config import ImapSettings
from mcp_mail.validators import (
    sanitize_attachment_filename,
    sanitize_imap_string,
    validate_imap_date,
    validate_imap_flags,
)

logger = logging.getLogger(__name__)


def _create_imap_client(settings: ImapSettings) -> aioimaplib.IMAP4_SSL | aioimaplib.IMAP4:
    if settings.use_ssl:
        ssl_context = ssl.create_default_context()
        if not settings.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        return aioimaplib.IMAP4_SSL(
            host=settings.host,
            port=settings.port,
            ssl_context=ssl_context,
            timeout=30,
        )
    return aioimaplib.IMAP4(host=settings.host, port=settings.port, timeout=30)


async def _connect(settings: ImapSettings) -> aioimaplib.IMAP4_SSL | aioimaplib.IMAP4:
    try:
        client = _create_imap_client(settings)
        await client.wait_hello_from_server()
        if settings.username and settings.password:
            await client.login(settings.username, settings.password.get_secret_value())
        return client
    except TimeoutError:
        raise ConnectionError(f"IMAP connection to {settings.host}:{settings.port} timed out")
    except OSError as e:
        raise ConnectionError(f"IMAP connection to {settings.host}:{settings.port} failed: {e}")


async def _disconnect(client: aioimaplib.IMAP4_SSL | aioimaplib.IMAP4) -> None:
    try:
        await client.logout()
    except Exception:
        pass


def _quote_mailbox(name: str) -> str:
    """RFC 3501 compliant mailbox name quoting."""
    # Escape backslashes and double quotes inside the name
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _parse_email_headers(raw: bytes) -> dict[str, Any]:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    has_attachments = False
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                has_attachments = True
                break
    return {
        "from": str(msg.get("From", "")),
        "to": str(msg.get("To", "")),
        "cc": str(msg.get("Cc", "")),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
        "message_id": str(msg.get("Message-ID", "")),
        "in_reply_to": str(msg.get("In-Reply-To", "")),
        "references": str(msg.get("References", "")),
        "has_attachments": has_attachments,
    }


def _parse_email_content(raw: bytes, max_body_length: int = 20000) -> dict[str, Any]:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    text_body = ""
    html_body = ""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                raw_filename = part.get_filename() or "unnamed"
                attachments.append({
                    "filename": sanitize_attachment_filename(raw_filename),
                    "content_type": content_type,
                    "size": len(part.get_payload(decode=True) or b""),
                })
            elif content_type == "text/plain" and not text_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    if len(text_body) > max_body_length:
        text_body = text_body[:max_body_length] + "\n[TRUNCATED]"
    if len(html_body) > max_body_length:
        html_body = html_body[:max_body_length] + "\n[TRUNCATED]"

    headers = _parse_email_headers(raw)
    return {
        **headers,
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachments,
    }


def _extract_uid_from_response(response_line: str) -> str | None:
    """Extract UID from IMAP FETCH response line like '1 FETCH (UID 123 ...)'."""
    if not isinstance(response_line, str):
        return None
    match = re.search(r"UID\s+(\d+)", response_line)
    return match.group(1) if match else None


def _extract_flags_from_response(response_line: str) -> list[str]:
    """Extract FLAGS from IMAP FETCH response line."""
    if not isinstance(response_line, str):
        return []
    match = re.search(r"FLAGS\s*\(([^)]*)\)", response_line)
    return match.group(1).split() if match else []


async def list_folders(settings: ImapSettings) -> list[dict]:
    client = await _connect(settings)
    try:
        status, data = await client.list("", "*")
        if status != "OK":
            raise RuntimeError(f"IMAP LIST failed: {status}")

        folders = []
        for line in data:
            if not isinstance(line, str) or not line.strip():
                continue
            # Parse IMAP LIST response: (\flags) "delimiter" "folder_name"
            # Use regex for reliable parsing
            match = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+"?([^"]*)"?', line)
            if match:
                folder_name = match.group(3).strip()
            else:
                # Fallback: try last quoted or unquoted token
                parts = line.rsplit('"', 2)
                if len(parts) >= 2 and parts[-2].strip():
                    folder_name = parts[-2].strip()
                else:
                    continue

            if not folder_name:
                continue

            unread = 0
            try:
                quoted = _quote_mailbox(folder_name)
                st, st_data = await client.status(quoted, "(UNSEEN)")
                if st == "OK" and st_data:
                    m = re.search(r"UNSEEN\s+(\d+)", str(st_data))
                    if m:
                        unread = int(m.group(1))
            except Exception:
                pass

            folders.append({"name": folder_name, "unread": unread})
        return folders
    finally:
        await _disconnect(client)


async def list_emails(
    settings: ImapSettings,
    mailbox: str = "INBOX",
    limit: int = 20,
    offset: int = 0,
    sender: str | None = None,
    subject: str | None = None,
    since: str | None = None,
    before: str | None = None,
    body_contains: str | None = None,
    flags: str | None = None,
) -> dict[str, Any]:
    client = await _connect(settings)
    try:
        status, _ = await client.select(_quote_mailbox(mailbox), readonly=True)
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox '{mailbox}'")

        # Build IMAP SEARCH criteria with sanitized inputs
        criteria = []
        if sender:
            criteria.append(f'FROM "{sanitize_imap_string(sender)}"')
        if subject:
            criteria.append(f'SUBJECT "{sanitize_imap_string(subject)}"')
        if since:
            criteria.append(f"SINCE {validate_imap_date(since)}")
        if before:
            criteria.append(f"BEFORE {validate_imap_date(before)}")
        if body_contains:
            criteria.append(f'BODY "{sanitize_imap_string(body_contains)}"')
        if flags:
            validated_flags = validate_imap_flags(flags)
            criteria.extend(validated_flags)

        search_str = " ".join(criteria) if criteria else "ALL"
        status, data = await client.search(search_str)
        if status != "OK":
            raise RuntimeError(f"IMAP SEARCH failed: {status}")

        uids = []
        for item in data:
            if isinstance(item, str) and item.strip():
                uids.extend(item.strip().split())
        uids.reverse()  # Newest first

        total_count = len(uids)
        page_uids = uids[offset : offset + limit]

        if not page_uids:
            return {"emails": [], "total_count": total_count, "has_more": offset + limit < total_count}

        # Fetch headers + flags + UID for page
        uid_str = ",".join(page_uids)
        status, data = await client.fetch(uid_str, "(UID BODY.PEEK[HEADER] FLAGS)")
        if status != "OK":
            raise RuntimeError(f"IMAP FETCH failed: {status}")

        emails = []
        i = 0
        while i < len(data):
            line = data[i]
            # Look for the response metadata line (contains UID and FLAGS)
            if isinstance(line, str) and "FETCH" in line:
                uid = _extract_uid_from_response(line)
                flags_list = _extract_flags_from_response(line)
                # Next item should be the raw bytes
                if i + 1 < len(data) and isinstance(data[i + 1], bytes):
                    raw = data[i + 1]
                    if raw:
                        headers = _parse_email_headers(raw)
                        headers["uid"] = uid or ""
                        headers["flags"] = flags_list
                        emails.append(headers)
                    i += 2
                    # Skip closing paren line if present
                    if i < len(data) and isinstance(data[i], str) and data[i].strip() == ")":
                        i += 1
                    continue
            i += 1

        return {
            "emails": emails,
            "total_count": total_count,
            "has_more": offset + limit < total_count,
        }
    finally:
        await _disconnect(client)


async def get_emails(
    settings: ImapSettings,
    uids: list[str],
    mailbox: str = "INBOX",
    max_body_length: int = 20000,
) -> list[dict]:
    client = await _connect(settings)
    try:
        status, _ = await client.select(_quote_mailbox(mailbox), readonly=True)
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox '{mailbox}'")

        uid_str = ",".join(uids)
        status, data = await client.fetch(uid_str, "(UID BODY.PEEK[])")
        if status != "OK":
            raise RuntimeError(f"IMAP FETCH failed: {status}")

        results = []
        i = 0
        while i < len(data):
            line = data[i]
            if isinstance(line, str) and "FETCH" in line:
                uid = _extract_uid_from_response(line)
                if i + 1 < len(data) and isinstance(data[i + 1], bytes):
                    raw = data[i + 1]
                    if raw:
                        content = _parse_email_content(raw, max_body_length)
                        content["uid"] = uid or ""
                        results.append(content)
                    i += 2
                    if i < len(data) and isinstance(data[i], str) and data[i].strip() == ")":
                        i += 1
                    continue
            i += 1

        return results
    finally:
        await _disconnect(client)


async def move_emails(
    settings: ImapSettings,
    uids: list[str],
    from_mailbox: str,
    to_mailbox: str,
) -> dict:
    client = await _connect(settings)
    try:
        status, _ = await client.select(_quote_mailbox(from_mailbox))
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox '{from_mailbox}'")

        uid_str = ",".join(uids)
        status, _ = await client.copy(uid_str, _quote_mailbox(to_mailbox))
        if status != "OK":
            raise RuntimeError(f"IMAP COPY to '{to_mailbox}' failed: {status}")

        await client.store(uid_str, "+FLAGS", r"(\Deleted)")
        await client.expunge()

        return {"moved": len(uids), "from": from_mailbox, "to": to_mailbox}
    finally:
        await _disconnect(client)


async def mark_emails(
    settings: ImapSettings,
    uids: list[str],
    mailbox: str,
    action: str,
) -> dict:
    client = await _connect(settings)
    try:
        status, _ = await client.select(_quote_mailbox(mailbox))
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox '{mailbox}'")

        uid_str = ",".join(uids)
        flag_map = {
            "read": ("+FLAGS", r"(\Seen)"),
            "unread": ("-FLAGS", r"(\Seen)"),
            "flagged": ("+FLAGS", r"(\Flagged)"),
            "unflagged": ("-FLAGS", r"(\Flagged)"),
        }
        if action not in flag_map:
            raise ValueError(f"Invalid action: {action}. Must be one of: {list(flag_map.keys())}")

        op, flags = flag_map[action]
        await client.store(uid_str, op, flags)

        return {"marked": len(uids), "action": action}
    finally:
        await _disconnect(client)


async def delete_emails(
    settings: ImapSettings,
    uids: list[str],
    mailbox: str,
) -> dict:
    client = await _connect(settings)
    try:
        status, _ = await client.select(_quote_mailbox(mailbox))
        if status != "OK":
            raise RuntimeError(f"Failed to select mailbox '{mailbox}'")

        uid_str = ",".join(uids)
        await client.store(uid_str, "+FLAGS", r"(\Deleted)")
        await client.expunge()

        return {"deleted": len(uids)}
    finally:
        await _disconnect(client)


async def _find_sent_folder(client) -> str | None:
    """Find the Sent folder by \\Sent attribute flag, then fallback to common names."""
    try:
        status, data = await client.list("", "*")
        if status != "OK":
            return None
        for line in data:
            if isinstance(line, str) and "\\Sent" in line:
                match = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+"?([^"]*)"?', line)
                if match:
                    return match.group(3).strip()
    except Exception:
        pass

    # Fallback: check if common folder names exist via STATUS (not SELECT)
    for name in ("Sent", "Sent Messages", "INBOX.Sent", "[Gmail]/Sent Mail"):
        try:
            st, _ = await client.status(_quote_mailbox(name), "(MESSAGES)")
            if st == "OK":
                return name
        except Exception:
            continue
    return None


async def append_to_sent(
    settings: ImapSettings,
    message: email.message.EmailMessage,
) -> None:
    """Save a sent email to the Sent folder via IMAP APPEND."""
    try:
        client = await _connect(settings)
    except Exception:
        logger.debug("Could not connect to IMAP for save-to-sent", exc_info=True)
        return
    try:
        sent_folder = await _find_sent_folder(client)
        if not sent_folder:
            logger.debug("Could not find Sent folder, skipping save-to-sent")
            return

        raw = message.as_bytes()
        await client.append(_quote_mailbox(sent_folder), raw, r"(\Seen)")
    except Exception:
        logger.debug("Failed to save to Sent folder", exc_info=True)
    finally:
        await _disconnect(client)


async def test_imap_connection(settings: ImapSettings) -> dict:
    client = await _connect(settings)
    try:
        return {"status": "connected", "host": settings.host, "port": settings.port}
    finally:
        await _disconnect(client)
