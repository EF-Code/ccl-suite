"""SMTP delivery for account invitations."""

from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.headerregistry import Address
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    """Raised when configured SMTP delivery cannot complete safely."""


def send_invitation_email(
    recipient: str,
    role: str,
    invite_url: str,
    expires_at: datetime,
) -> bool:
    """Send an invitation when SMTP is configured; return false if disabled."""

    host = os.getenv("CCL_SMTP_HOST", "").strip()
    if not host:
        return False

    try:
        port = int(os.getenv("CCL_SMTP_PORT", "1025"))
    except ValueError as exc:
        raise EmailDeliveryError("SMTP port configuration is invalid.") from exc
    if not 1 <= port <= 65535:
        raise EmailDeliveryError("SMTP port configuration is invalid.")

    username = os.getenv("CCL_SMTP_USERNAME", "")
    password = os.getenv("CCL_SMTP_PASSWORD", "")
    if bool(username) != bool(password):
        raise EmailDeliveryError("SMTP username and password must be configured together.")

    starttls_value = os.getenv("CCL_SMTP_STARTTLS", "false").strip().casefold()
    if starttls_value not in {"true", "false", "1", "0", "yes", "no"}:
        raise EmailDeliveryError("SMTP STARTTLS configuration is invalid.")
    use_starttls = starttls_value in {"true", "1", "yes"}
    if username and not use_starttls:
        raise EmailDeliveryError("SMTP STARTTLS is required when SMTP authentication is configured.")

    from_address = os.getenv("CCL_MAIL_FROM_ADDRESS", "no-reply@example.test").strip()
    if not from_address or "\r" in from_address or "\n" in from_address or "@" not in from_address:
        raise EmailDeliveryError("Email sender address configuration is invalid.")

    expiry = expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    expiry_text = expiry.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    try:
        message = EmailMessage()
        message["From"] = Address(display_name="CCL Suite", addr_spec=from_address)
        message["To"] = recipient
        message["Subject"] = "You are invited to CCL Suite"
        message.set_content(
            "You have been invited to join CCL Suite.\n\n"
            f"Role: {role}\n"
            f"Accept your invitation before {expiry_text}:\n{invite_url}\n\n"
            "If you were not expecting this invitation, you can ignore this email."
        )
        safe_url = html.escape(invite_url, quote=True)
        message.add_alternative(
            "<p>You have been invited to join <strong>CCL Suite</strong>.</p>"
            f"<p>Role: {html.escape(role)}</p>"
            f"<p>This invitation expires at {html.escape(expiry_text)}.</p>"
            f'<p><a href="{safe_url}">Accept invitation</a></p>'
            "<p>If you were not expecting this invitation, you can ignore this email.</p>",
            subtype="html",
        )
    except (TypeError, ValueError) as exc:
        raise EmailDeliveryError("Email message configuration is invalid.") from exc

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if use_starttls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise EmailDeliveryError("Invitation email could not be delivered.") from exc
    return True


__all__ = ["EmailDeliveryError", "send_invitation_email"]
