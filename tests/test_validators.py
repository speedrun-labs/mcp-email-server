import pytest

from mcp_mail.validators import (
    check_allowed_domains,
    check_max_recipients,
    render_template,
    sanitize_subject,
    validate_email_address,
    validate_email_list,
)


def test_validate_email_valid():
    result = validate_email_address("test@example.com")
    assert result == "test@example.com"


def test_validate_email_invalid():
    with pytest.raises(Exception):
        validate_email_address("not-an-email")


def test_validate_email_list():
    result = validate_email_list("a@b.com, c@d.com")
    assert result == ["a@b.com", "c@d.com"]


def test_validate_email_list_empty():
    assert validate_email_list("") == []
    assert validate_email_list(None) == []


def test_sanitize_subject_strips_newlines():
    assert sanitize_subject("Hello\r\nWorld") == "Hello  World"


def test_sanitize_subject_max_length():
    long_subject = "x" * 2000
    result = sanitize_subject(long_subject)
    assert len(result) == 998


def test_check_allowed_domains_pass():
    check_allowed_domains(["a@example.com"], ["example.com"])


def test_check_allowed_domains_fail():
    with pytest.raises(ValueError, match="not in the allowed"):
        check_allowed_domains(["a@evil.com"], ["example.com"])


def test_check_allowed_domains_empty():
    check_allowed_domains(["a@anything.com"], [])  # No restrictions


def test_check_max_recipients_pass():
    check_max_recipients(["a@b.com"], ["c@d.com"], [], 5)


def test_check_max_recipients_fail():
    with pytest.raises(ValueError, match="exceeds maximum"):
        check_max_recipients(["a@b.com", "c@d.com"], [], [], 1)


def test_render_template():
    result = render_template("Hello {{name}}, order {{id}}", {"name": "Alice", "id": "123"})
    assert result == "Hello Alice, order 123"


def test_render_template_missing_var():
    with pytest.raises(ValueError, match="Unresolved"):
        render_template("Hello {{name}}", {})


def test_render_template_no_vars():
    result = render_template("No variables here", {})
    assert result == "No variables here"
