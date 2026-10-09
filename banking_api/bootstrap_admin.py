import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from banking_api.database import configure_database
from banking_api.models import StaffUser
from banking_api.security import hash_password
from banking_api.settings import Settings


def main():
    settings = Settings.from_environment()
    engine = configure_database(settings)
    with Session(engine) as session:
        if session.scalar(select(StaffUser.id).limit(1)) is not None:
            raise SystemExit(
                "Staff accounts already exist. Use the authenticated staff API "
                "to manage additional staff."
            )
        full_name = input("First administrator full name: ").strip()
        username = input("Username: ").strip().casefold()
        password = getpass.getpass("Password (12+ characters): ")
        confirmation = getpass.getpass("Confirm password: ")
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
        if password != confirmation:
            raise SystemExit("Passwords did not match.")
        session.add(
            StaffUser(
                username=username,
                full_name=full_name,
                role="ADMIN",
                password_hash=hash_password(password),
            )
        )
        session.commit()
    print("Initial administrator created.")


if __name__ == "__main__":
    main()
