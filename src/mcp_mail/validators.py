from __future__ import annotations

import re

from email_validator import EmailNotValidError, validate_email


def validate_email_address(address: str) -> str:
    """Validate and normalize an email address. Returns normalized address."""
    result = validate_email(address, check_deliverability=False)
    return result.normalized


def validate_email_list(addresses: str) -> list[str]:
    """Validate comma-separated email addresses. Returns list of normalized addresses."""
    if not addresses or not addresses.strip():
        return []
    result = []
    for addr in addresses.split(","):
        addr = addr.strip()
        if addr:
            result.append(validate_email_address(addr))
    return result


def sanitize_subject(subject: str, max_length: int = 998) -> str:
    """Strip newlines to prevent header injection and enforce max length."""
    cleaned = re.sub(r"[\r\n]", " ", subject)
    return cleaned[:max_length]


def check_allowed_domains(addresses: list[str], allowed_domains: list[str]) -> None:
    """Raise ValueError if any address is outside the allowed domains."""
    if not allowed_domains:
        return
    allowed = {d.lower() for d in allowed_domains}
    for addr in addresses:
        domain = addr.rsplit("@", 1)[-1].lower()
        if domain not in allowed:
            raise ValueError(f"Domain '{domain}' is not in the allowed domains list")


def check_max_recipients(
    to: list[str], cc: list[str], bcc: list[str], max_recipients: int
) -> None:
    """Raise ValueError if total recipients exceed the cap."""
    total = len(to) + len(cc) + len(bcc)
    if total > max_recipients:
        raise ValueError(f"Total recipients ({total}) exceeds maximum ({max_recipients})")


_IMAP_DATE_RE = re.compile(r"^\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{4}$")
_VALID_IMAP_FLAGS = {"SEEN", "UNSEEN", "FLAGGED", "UNFLAGGED", "ANSWERED", "DELETED", "DRAFT"}


def sanitize_imap_string(value: str, max_length: int = 200) -> str:
    """Sanitize a string for use in IMAP SEARCH commands.

    Removes characters that could cause IMAP command injection:
    double quotes, backslashes, newlines, and null bytes.
    """
    if not value:
        return value
    value = value[:max_length]
    # Remove characters that break IMAP quoted strings
    value = re.sub(r'["\\\r\n\x00]', "", value)
    return value


def validate_imap_date(date_str: str) -> str:
    """Validate IMAP date format (DD-Mon-YYYY). Raises ValueError if invalid."""
    if not _IMAP_DATE_RE.match(date_str):
        raise ValueError(f"Invalid IMAP date format: '{date_str}'. Expected DD-Mon-YYYY (e.g., 01-Jan-2026)")
    return date_str


def validate_imap_flags(flags_str: str) -> list[str]:
    """Validate and parse comma-separated IMAP flag names."""
    result = []
    for flag in flags_str.split(","):
        flag = flag.strip().upper()
        if flag and flag in _VALID_IMAP_FLAGS:
            result.append(flag)
        elif flag:
            raise ValueError(f"Invalid IMAP flag: '{flag}'. Valid: {sorted(_VALID_IMAP_FLAGS)}")
    return result


def sanitize_attachment_filename(filename: str) -> str:
    """Remove path traversal and dangerous characters from filenames."""
    import os
    # Remove path components
    filename = os.path.basename(filename)
    # Remove null bytes and control characters
    filename = re.sub(r"[\x00-\x1f]", "", filename)
    return filename or "unnamed"


def render_template(template: str, variables: dict[str, str]) -> str:
    """Replace {{variable}} placeholders in template string."""
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    # Check for remaining unresolved placeholders
    remaining = re.findall(r"\{\{(\w+)\}\}", result)
    if remaining:
        raise ValueError(f"Unresolved template variables: {remaining}")
    return result
