import argparse
import getpass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from banking_api.database import configure_database
from banking_api.models import StaffUser
from banking_api.security import hash_password
from banking_api.settings import Settings

DEFAULT_ADMIN_PASSWORD = "shiva@12345678"


def validate_password(password):
    if len(password) < 12 or len(password) > 256:
        raise SystemExit("Password must be between 12 and 256 characters.")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Administrator for Banking System")
    admin_action = parser.add_mutually_exclusive_group()
    admin_action.add_argument(
        "--seed-shiva", action="store_true", help="Create the initial Shiva admin if absent"
    )
    admin_action.add_argument(
        "--reset-shiva", action="store_true", help="Explicitly reset the Shiva admin password"
    )
    parser.add_argument("--username", help="Administrator username")
    parser.add_argument("--full-name", help="Administrator full name")
    parser.add_argument("--password", help="Administrator password")
    args = parser.parse_args()

    settings = Settings.from_environment()
    engine = configure_database(settings)

    with Session(engine) as session:
        if args.seed_shiva or args.reset_shiva:
            username = "shiva"
            full_name = "Shiva Chaurasiya"
            existing = session.scalar(
                select(StaffUser).where(StaffUser.username == username)
            )
            if args.seed_shiva and existing:
                print("Administrator 'shiva' already exists; no changes were made.")
                return
            if args.reset_shiva and existing is None:
                raise SystemExit("Administrator 'shiva' does not exist; run --seed-shiva first.")

            password = args.password or DEFAULT_ADMIN_PASSWORD
            validate_password(password)
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
        validate_password(password)

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
