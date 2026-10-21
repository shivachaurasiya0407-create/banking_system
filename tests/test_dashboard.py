import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from banking_api.app import app
from banking_api.auth import get_current_staff, get_db, get_settings
from banking_api.models import Account, Base, Branch, Customer, StaffUser
from banking_api.settings import Settings


@pytest.fixture
def dashboard_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    actor = StaffUser(
        id=uuid.uuid4(),
        username="admin",
        full_name="Demo Admin",
        role="ADMIN",
        password_hash="unused",
    )
    first_customer = Customer(
        id=uuid.uuid4(),
        first_name="Asha",
        last_name="Sharma",
        phone="9999999999",
        age=30,
        country="India",
        state="Delhi",
        identity_fingerprint="a" * 64,
    )
    second_customer = Customer(
        id=uuid.uuid4(),
        first_name="Ravi",
        last_name="Verma",
        phone="8888888888",
        age=35,
        country="India",
        state="Punjab",
        identity_fingerprint="b" * 64,
    )
    settings = Settings(
        database_url="sqlite://",
        jwt_secret="test-jwt-secret-at-least-thirty-two-bytes",
        pii_hmac_key="test-pii-hmac-secret-at-least-32-bytes",
        jwt_issuer="banking-system-test",
        access_token_minutes=15,
        login_max_attempts=5,
        login_lockout_minutes=15,
    )
    session.add_all(
        [
            actor,
            first_customer,
            second_customer,
            Branch(ifsc="SHIV0000001", name="Main Branch", next_sequence=1),
            Branch(ifsc="SHIV0000002", name="Demo Branch", next_sequence=1),
            Account(
                id=uuid.uuid4(),
                customer_id=first_customer.id,
                account_number="1000000001",
                ifsc="SHIV0000001",
                branch_sequence=1,
                status="ACTIVE",
                balance_minor=250_000,
            ),
            Account(
                id=uuid.uuid4(),
                customer_id=second_customer.id,
                account_number="1000000002",
                ifsc="SHIV0000001",
                branch_sequence=2,
                status="FROZEN",
                balance_minor=100_500,
            ),
        ]
    )
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_staff] = lambda: actor
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, actor, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_dashboard_summary_reads_live_database_counts(dashboard_client):
    client, _, _ = dashboard_client

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    assert response.json() == {
        "accounts": {"total": 2, "active": 1, "frozen": 1, "closed": 0},
        "total_balance": "3505.00",
        "transactions": 0,
    }


def test_account_search_matches_customer_name_and_escapes_wildcards(dashboard_client):
    client, _, _ = dashboard_client

    match = client.get("/accounts", params={"q": "Asha"})
    wildcard = client.get("/accounts", params={"q": "%"})

    assert match.status_code == 200
    assert [item["account_number"] for item in match.json()["items"]] == [
        "1000000001"
    ]
    assert wildcard.status_code == 200
    assert wildcard.json()["items"] == []


def test_current_staff_and_branch_routes(dashboard_client):
    client, _, _ = dashboard_client

    assert client.get("/auth/me").json() == {
        "id": str(dashboard_client[1].id),
        "username": "admin",
        "full_name": "Demo Admin",
        "role": "ADMIN",
    }
    assert client.get("/branches").json() == [
        {"ifsc": "SHIV0000002", "name": "Demo Branch"},
        {"ifsc": "SHIV0000001", "name": "Main Branch"},
    ]
    assert client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Demo Branch 3"}
    ).status_code == 201
    duplicate = client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Duplicate"}
    )
    assert duplicate.status_code == 409


def test_account_opening_uses_selected_database_branch(dashboard_client):
    client, _, session = dashboard_client

    response = client.post(
        "/accounts",
        headers={"Idempotency-Key": "branch-account-setup-test"},
        json={
            "customer": {
                "first_name": "Mira",
                "last_name": "Kapoor",
                "phone": "7777777777",
                "age": 28,
                "country": "India",
                "state": "Delhi",
                "identity_number": "123456789012",
            },
            "opening_deposit": "2000.00",
            "branch_ifsc": "SHIV0000002",
        },
    )

    assert response.status_code == 201
    account = session.query(Account).filter_by(
        account_number=response.json()["account_numbers"][0]
    ).one()
    assert account.ifsc == "SHIV0000002"


def test_teller_cannot_create_branches(dashboard_client):
    client, actor, _ = dashboard_client
    actor.role = "TELLER"

    response = client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Restricted Branch"}
    )

    assert response.status_code == 403


def test_audit_logs_endpoint(dashboard_client):
    client, _, _ = dashboard_client
    response = client.get("/admin/audit-logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_statement_json_endpoint(dashboard_client):
    client, _, _ = dashboard_client
    response = client.get("/accounts/1000000001/statement")
    assert response.status_code == 200
    data = response.json()
    assert data["account_number"] == "1000000001"
    assert "entries" in data
    assert "current_balance" in data
