"""Invite-only account credentials and opaque, revocable session tokens."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.orm import Session

from models import AuthSession, AuthThrottle, Invitation, User, utc_now

INVITATION_LIFETIME = timedelta(days=3)
SESSION_LIFETIME = timedelta(hours=12)
LOGIN_WINDOW = timedelta(minutes=15)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)
DUMMY_HASH = PASSWORD_HASHER.hash("unusable-password-for-unknown-account")


def normalize_email(value: str) -> str:
    """Normalize a login address without accepting whitespace or control bytes."""

    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(value: str) -> str:
    """Require a bounded passphrase; Argon2id protects its stored representation."""

    if len(value) < 12 or len(value) > 1024 or "\x00" in value:
        raise ValueError("Password must contain 12 to 1024 characters.")
    return value


def hash_password(value: str) -> str:
    return PASSWORD_HASHER.hash(validate_password(value))


def verify_password(value: str, stored_hash: str | None) -> bool:
    try:
        return bool(PASSWORD_HASHER.verify(stored_hash or DUMMY_HASH, value)) and bool(stored_hash)
    except (VerificationError, InvalidHashError):
        return False


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    """SQLite drops timezone information; treat stored timestamps as UTC."""

    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def issue_invitation(email: str, role: str, invited_by: User) -> tuple[Invitation, str]:
    token = secrets.token_urlsafe(32)
    return (
        Invitation(
            email=normalize_email(email),
            role=role,
            token_hash=token_digest(token),
            invited_by_id=invited_by.id,
            expires_at=utc_now() + INVITATION_LIFETIME,
        ),
        token,
    )


def invitation_is_valid(invitation: Invitation) -> bool:
    return (
        invitation.accepted_at is None
        and invitation.revoked_at is None
        and as_utc(invitation.expires_at) > utc_now()
    )


def issue_session(user: User) -> tuple[AuthSession, str, str]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    return (
        AuthSession(
            token_hash=token_digest(session_token),
            csrf_hash=token_digest(csrf_token),
            user_id=user.id,
            expires_at=utc_now() + SESSION_LIFETIME,
        ),
        session_token,
        csrf_token,
    )


def session_is_valid(session: AuthSession) -> bool:
    return session.revoked_at is None and as_utc(session.expires_at) > utc_now()


def login_is_throttled(db: Session, email: str, client_ip: str) -> bool:
    now = utc_now()
    for key in (f"email:{email}", f"ip:{client_ip}"):
        throttle = db.get(AuthThrottle, token_digest(key))
        if throttle is not None and throttle.locked_until is not None:
            if as_utc(throttle.locked_until) > now:
                return True
    return False


def record_failed_login(db: Session, email: str, client_ip: str) -> None:
    now = utc_now()
    for key, limit in ((f"email:{email}", 5), (f"ip:{client_ip}", 25)):
        digest = token_digest(key)
        throttle = db.get(AuthThrottle, digest)
        if throttle is None:
            throttle = AuthThrottle(key_hash=digest, failures=0, window_started=now)
            db.add(throttle)
        elif as_utc(throttle.window_started) + LOGIN_WINDOW <= now:
            throttle.failures = 0
            throttle.window_started = now
            throttle.locked_until = None
        throttle.failures += 1
        if throttle.failures >= limit:
            throttle.locked_until = now + LOGIN_WINDOW
    db.commit()


def clear_email_login_failures(db: Session, email: str) -> None:
    throttle = db.get(AuthThrottle, token_digest(f"email:{email}"))
    if throttle is not None:
        db.delete(throttle)


__all__ = [
    "as_utc",
    "clear_email_login_failures",
    "hash_password",
    "invitation_is_valid",
    "issue_invitation",
    "issue_session",
    "login_is_throttled",
    "normalize_email",
    "record_failed_login",
    "session_is_valid",
    "token_digest",
    "validate_password",
    "verify_password",
]
