"""Create the first administrator once, using a password prompt (not shell args)."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth import hash_password, normalize_email  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Administrator email address")
    args = parser.parse_args()
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        parser.error(str(exc))

    with SessionLocal() as db:
        existing_admin = db.scalar(
            select(User.id).where(
                User.role == "administrator",
                User.is_active.is_(True),
                User.password_hash.is_not(None),
            )
        )
        if existing_admin is not None:
            parser.error("An active administrator already exists; use invitations instead.")
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            parser.error("An account already uses this email.")
        password = getpass.getpass("New administrator password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            parser.error("Passwords do not match.")
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            parser.error(str(exc))
        account = User(
            external_ref=f"account:{uuid4().hex}",
            email=email,
            password_hash=password_hash,
            is_active=True,
            role="administrator",
        )
        db.add(account)
        db.commit()
        print(f"Administrator created for {email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
