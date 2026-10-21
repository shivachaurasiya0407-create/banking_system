import argparse
import getpass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from banking_api.database import configure_database
from banking_api.models import StaffUser
from banking_api.security import hash_password
from banking_api.settings import Settings


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Administrator for Banking System")
    parser.add_argument(
        "--seed-shiva",
        action="store_true",
        help="Seed default admin 'shiva' (Shiva Chaurasiya)",
    )
    parser.add_argument("--username", help="Administrator username")
    parser.add_argument("--full-name", help="Administrator full name")
    parser.add_argument("--password", help="Administrator password")
    args = parser.parse_args()

    settings = Settings.from_environment()
    engine = configure_database(settings)

    with Session(engine) as session:
        if args.seed_shiva:
            username = "shiva"
            full_name = "Shiva Chaurasiya"
            password = args.password or "Shiva@12345678"
            existing = session.scalar(
                select(StaffUser).where(StaffUser.username == username)
            )
            if existing:
                existing.full_name = full_name
                existing.password_hash = hash_password(password)
                existing.active = True
                existing.role = "ADMIN"
                existing.token_version += 1
                existing.failed_login_attempts = 0
                existing.locked_until = None
                session.commit()
                print(
                    f"Administrator '{username}' (Shiva Chaurasiya) updated successfully in PostgreSQL."
                )
                return
            new_admin = StaffUser(
                id=uuid.uuid4(),
                username=username,
                full_name=full_name,
                role="ADMIN",
                password_hash=hash_password(password),
                active=True,
            )
            session.add(new_admin)
            session.commit()
            print(
                f"Administrator '{username}' (Shiva Chaurasiya) created successfully in PostgreSQL."
            )
            return

        if args.username and args.full_name and args.password:
            username = args.username.strip().casefold()
            full_name = args.full_name.strip()
            password = args.password
        else:
            first_user = session.scalar(select(StaffUser.id).limit(1))
            if first_user is not None:
                print("Notice: Staff accounts already exist in PostgreSQL.")
                choice = (
                    input("Do you want to create or reset an admin account? [y/N]: ")
                    .strip()
                    .lower()
                )
                if choice not in ("y", "yes"):
                    raise SystemExit("Cancelled.")
            full_name = input("Administrator full name: ").strip()
            username = input("Username: ").strip().casefold()
            password = getpass.getpass("Password (12+ characters): ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise SystemExit("Passwords did not match.")

        if not full_name or not username:
            raise SystemExit("Full name and username are required.")
        if (
            len(password) < 12
            or not any(char.isupper() for char in password)
            or not any(char.islower() for char in password)
            or not any(char.isdigit() for char in password)
        ):
            raise SystemExit(
                "Password must be at least 12 characters and include "
                "uppercase, lowercase, and numeric characters."
            )

        existing = session.scalar(
            select(StaffUser).where(StaffUser.username == username)
        )
        if existing:
            existing.full_name = full_name
            existing.password_hash = hash_password(password)
            existing.active = True
            existing.role = "ADMIN"
            existing.token_version += 1
            existing.failed_login_attempts = 0
            existing.locked_until = None
            session.commit()
            print(f"Administrator '{username}' updated successfully in PostgreSQL.")
            return

        session.add(
            StaffUser(
                id=uuid.uuid4(),
                username=username,
                full_name=full_name,
                role="ADMIN",
                password_hash=hash_password(password),
                active=True,
            )
        )
        session.commit()
        print(f"Administrator '{username}' created successfully in PostgreSQL.")


if __name__ == "__main__":
    main()
