"""Reset an existing active account password from the trusted local host."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import hash_password, normalize_email  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import AuthSession, PasswordResetToken, SecurityEvent, User, utc_now  # noqa: E402


def reset_account_password(db: Session, email: str, new_password: str) -> tuple[str, int, str]:
    """Set a password for an active account, revoke its sessions, and audit it."""

    normalized_email = normalize_email(email)
    user = db.scalar(
        select(User).where(User.email == normalized_email).with_for_update()
    )
    if user is None or not user.is_active or not user.password_hash:
        raise ValueError("No active password-enabled account matches that email.")

    new_password_hash = hash_password(new_password)
    reset_time = utc_now()
    active_sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()

    user.password_hash = new_password_hash
    for session in active_sessions:
        session.revoked_at = reset_time
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=reset_time)
    )

    audit_reference = str(uuid4())
    db.add(
        SecurityEvent(
            actor_id=None,
            event_code="auth.password.reset",
            outcome="success",
            resource_type="user",
            resource_ref=str(user.id),
            request_ref=audit_reference,
        )
    )
    db.commit()
    return str(user.id), len(active_sessions), audit_reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing active account")
    args = parser.parse_args()
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        parser.error(str(exc))

    confirmation = input(f"Type RESET {email} to continue: ")
    if confirmation != f"RESET {email}":
        parser.error("Account reset was not confirmed.")

    password = getpass.getpass("New account password: ")
    repeated_password = getpass.getpass("Confirm new account password: ")
    if password != repeated_password:
        parser.error("Passwords do not match.")

    try:
        with SessionLocal() as db:
            user_id, revoked_sessions, audit_reference = reset_account_password(
                db, email, password
            )
    except ValueError as exc:
        parser.error(str(exc))

    print(
        "Account password reset completed. "
        f"User ID: {user_id}; sessions revoked: {revoked_sessions}; "
        f"audit reference: {audit_reference}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
