from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage

from mail_delivery import send_invitation_email, send_password_reset_email


class CapturingSMTP:
    messages: list[EmailMessage] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        assert host == "mailpit"
        assert port == 1025
        assert timeout == 10

    def __enter__(self) -> CapturingSMTP:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


def test_account_emails_share_smtp_and_reset_message_is_short_lived(
    monkeypatch,
) -> None:
    CapturingSMTP.messages = []
    monkeypatch.setenv("CCL_SMTP_HOST", "mailpit")
    monkeypatch.setenv("CCL_SMTP_PORT", "1025")
    monkeypatch.setenv("CCL_SMTP_STARTTLS", "false")
    monkeypatch.setenv("CCL_SMTP_USERNAME", "")
    monkeypatch.setenv("CCL_SMTP_PASSWORD", "")
    monkeypatch.setenv("CCL_MAIL_FROM_ADDRESS", "no-reply@example.test")
    monkeypatch.setattr("mail_delivery.smtplib.SMTP", CapturingSMTP)

    expiry = datetime(2026, 10, 6, 11, 30, tzinfo=timezone.utc)
    assert send_invitation_email(
        "staff@example.test",
        "staff",
        "http://127.0.0.1:8000/#invite=opaque-token",
        expiry,
    )
    reset_url = "http://127.0.0.1:8000/#reset=opaque-token"
    assert send_password_reset_email("staff@example.test", reset_url, expiry)

    invitation, reset = CapturingSMTP.messages
    assert invitation["Subject"] == "You are invited to CCL Suite"
    assert reset["Subject"] == "Reset your CCL Suite password"
    plain = reset.get_body(preferencelist=("plain",)).get_content()
    html_body = reset.get_body(preferencelist=("html",)).get_content()
    assert reset_url in plain
    assert "2026-10-06 11:30 UTC" in plain
    assert "Your existing password will remain active" in plain
    assert 'href="http://127.0.0.1:8000/#reset=opaque-token"' in html_body
