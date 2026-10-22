import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from banking_api import bootstrap_admin
from banking_api.models import Base, Customer, StaffUser
from banking_api.schemas import (
    StaffChangePasswordRequest,
    StaffCreateRequest,
    StaffPasswordResetRequest,
)
from banking_api.security import hash_password, verify_password


@pytest.fixture
def bootstrap_engine(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        bootstrap_admin.Settings,
        "from_environment",
        staticmethod(lambda: object()),
    )
    monkeypatch.setattr(bootstrap_admin, "configure_database", lambda settings: engine)
    yield engine
    engine.dispose()


def run_bootstrap(monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", ["bootstrap_admin", *arguments])
    bootstrap_admin.main()


def test_seed_creates_only_initial_admin(bootstrap_engine, monkeypatch):
    run_bootstrap(monkeypatch, "--seed-shiva")

    with Session(bootstrap_engine) as session:
        admin = session.scalar(select(StaffUser).where(StaffUser.username == "shiva"))
        assert admin is not None
        assert admin.full_name == "Shiva Chaurasiya"
        assert admin.role == "ADMIN"
        assert verify_password(bootstrap_admin.DEFAULT_ADMIN_PASSWORD, admin.password_hash)
        assert session.scalar(select(Customer.id)) is None
        assert len(session.scalars(select(StaffUser)).all()) == 1


def test_repeated_seed_does_not_reset_existing_admin(bootstrap_engine, monkeypatch):
    run_bootstrap(monkeypatch, "--seed-shiva")

    with Session(bootstrap_engine) as session:
        admin = session.scalar(select(StaffUser).where(StaffUser.username == "shiva"))
        admin.password_hash = hash_password("a different secure password")
        admin.full_name = "Updated Name"
        session.commit()

    run_bootstrap(monkeypatch, "--seed-shiva")

    with Session(bootstrap_engine) as session:
        admin = session.scalar(select(StaffUser).where(StaffUser.username == "shiva"))
        assert admin.full_name == "Updated Name"
        assert verify_password("a different secure password", admin.password_hash)


def test_reset_shiva_requires_explicit_flag(bootstrap_engine, monkeypatch):
    run_bootstrap(monkeypatch, "--seed-shiva")
    run_bootstrap(monkeypatch, "--reset-shiva")

    with Session(bootstrap_engine) as session:
        admin = session.scalar(select(StaffUser).where(StaffUser.username == "shiva"))
        assert verify_password(bootstrap_admin.DEFAULT_ADMIN_PASSWORD, admin.password_hash)


def test_initial_password_is_accepted_for_staff_password_workflows():
    password = bootstrap_admin.DEFAULT_ADMIN_PASSWORD

    assert len(password) >= 12
    StaffCreateRequest(
        username="newstaff",
        full_name="New Staff",
        role="TELLER",
        password=password,
    )
    StaffChangePasswordRequest(current_password="old-password", new_password=password)
    StaffPasswordResetRequest(password=password)
