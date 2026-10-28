"""Owner-only user provisioning; passwords come from getpass or explicit stdin."""

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import LoginRequest
from app.db.session import get_engine
from app.models.auth import AuthSession, User
from app.services.auth_service import PASSWORDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["create", "disable", "reset-password", "set-role", "purge-sessions"]
    )
    parser.add_argument("--email")
    parser.add_argument("--role", choices=["admin", "viewer"])
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    if args.action != "purge-sessions" and not args.email:
        parser.error("--email is required")
    if args.action in {"create", "set-role"} and not args.role:
        parser.error("--role is required")
    email = LoginRequest(email=args.email, password="validation-only").email if args.email else None
    password = None
    if args.action in {"create", "reset-password"}:
        password = (
            sys.stdin.readline().rstrip("\r\n")
            if args.password_stdin
            else getpass.getpass("Password: ")
        )
        if not args.password_stdin and password != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords do not match")
        if len(password) < 12 or len(password.encode()) > 1024:
            raise SystemExit(
                "Use a password of at least 12 characters and at most 1024 UTF-8 bytes"
            )
    with Session(get_engine()) as db:
        if args.action == "purge-sessions":
            from sqlalchemy import delete

            db.execute(delete(AuthSession).where(AuthSession.expires_at < datetime.now(UTC)))
            db.commit()
            print("Expired session records removed")
            return
        user = db.scalar(select(User).where(User.email == email))
        if args.action == "create":
            if user:
                raise SystemExit("User already exists; nothing changed")
            db.add(User(email=email, password_hash=PASSWORDS.hash(password), role=args.role))
        else:
            if not user:
                raise SystemExit("User not found; nothing changed")
            if args.action == "disable":
                user.is_active = False
            elif args.action == "set-role":
                user.role = args.role
            else:
                user.password_hash = PASSWORDS.hash(password)
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user.id)
                .values(revoked_at=datetime.now(UTC))
            )
        db.commit()
    print("User operation completed; no password or token was logged")


if __name__ == "__main__":
    main()
