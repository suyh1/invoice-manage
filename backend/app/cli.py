from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.domain.user.models import UserRole
from app.domain.user.service import create_user


def main() -> None:
    parser = argparse.ArgumentParser(prog="invoice-app")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin = subparsers.add_parser("create-admin")
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--password", required=True)
    create_admin.add_argument("--display-name", default="Administrator")

    args = parser.parse_args()
    if args.command == "create-admin":
        with SessionLocal() as db:
            user = create_user(
                db,
                email=args.email,
                password=args.password,
                display_name=args.display_name,
                role=UserRole.admin,
            )
            db.commit()
            print(f"created admin user {user.email}")


if __name__ == "__main__":
    main()
