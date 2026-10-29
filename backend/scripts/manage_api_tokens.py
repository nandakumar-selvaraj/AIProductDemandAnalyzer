"""Owner-only API token issuance/revocation. Never print a credential to stdout."""

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import LoginRequest
from app.core.config import get_settings
from app.db.session import get_engine
from app.models.auth import ApiToken, User
from app.services.auth_service import issue_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["issue", "revoke"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--minutes", type=int, default=10, choices=range(1, 16))
    parser.add_argument("--output", type=Path, help="New private token file (never overwritten)")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.auth_enabled:
        parser.error("AUTH_ENABLED=true is required")
    if args.action == "issue" and not args.output:
        parser.error("--output is required for issuance")
    email = LoginRequest(email=args.email, password="validation-only").email
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.is_active:
            raise SystemExit("Active user not found; nothing changed")
        if args.action == "revoke":
            db.execute(
                update(ApiToken)
                .where(ApiToken.user_id == user.id)
                .values(revoked_at=datetime.now(UTC))
            )
            db.commit()
            print("API tokens revoked for this user; browser sessions unchanged")
            return
        # O_EXCL prevents clobbering/symlink following; POSIX permissions are owner-only.
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        principal = None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                token, principal = issue_session(db, user, settings, api_minutes=args.minutes)
                output.write(token + "\n")
        except BaseException:
            if principal is not None:
                db.execute(
                    update(ApiToken)
                    .where(ApiToken.id == principal.session_id)
                    .values(revoked_at=datetime.now(UTC))
                )
                db.commit()
            args.output.unlink(missing_ok=True)
            raise
    print(f"API token saved privately; expires {principal.expires_at.isoformat()}")


if __name__ == "__main__":
    main()
