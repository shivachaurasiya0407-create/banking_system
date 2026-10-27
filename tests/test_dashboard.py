import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from banking_api.app import app
from banking_api.auth import get_current_staff, get_db, get_settings
from banking_api.models import (
    Account,
    AuditEvent,
    Base,
    Branch,
    Customer,
    LedgerAccount,
    LedgerTransaction,
    StaffUser,
)
from banking_api.security import hash_password
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
        full_name="DEMO ADMIN",
        role="ADMIN",
        password_hash="unused",
    )
    first_customer = Customer(
        id=uuid.uuid4(),
        first_name="ASHA",
        last_name="SHARMA",
        phone="9999999999",
        age=30,
        country="INDIA",
        state="DELHI",
        identity_fingerprint="a" * 64,
        kyc_status="VERIFIED",
    )
    second_customer = Customer(
        id=uuid.uuid4(),
        first_name="RAVI",
        last_name="VERMA",
        phone="8888888888",
        age=35,
        country="INDIA",
        state="PUNJAB",
        identity_fingerprint="b" * 64,
        kyc_status="VERIFIED",
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
            Branch(ifsc="SHIV0000001", name="MAIN BRANCH", next_sequence=1),
            Branch(ifsc="SHIV0000002", name="DEMO BRANCH", next_sequence=1),
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
        "loans": {
            "active": 0,
            "applied": 0,
            "approved": 0,
            "outstanding": "0.00",
        },
        "fixed_deposits": {"active": 0, "total_value": "0.00"},
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


def test_cors_allows_banking_session_header_for_browser_clients(dashboard_client):
    client, _, _ = dashboard_client

    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Banking-Session",
        },
    )

    assert response.status_code == 200
    assert "X-Banking-Session" in response.headers.get("access-control-allow-headers", "")


def test_current_staff_and_branch_routes(dashboard_client):
    client, _, _ = dashboard_client

    assert client.get("/auth/me").json() == {
        "id": str(dashboard_client[1].id),
        "username": "admin",
        "full_name": "DEMO ADMIN",
        "role": "ADMIN",
    }
    assert client.get("/branches").json() == [
        {"ifsc": "SHIV0000002", "name": "DEMO BRANCH"},
        {"ifsc": "SHIV0000001", "name": "MAIN BRANCH"},
    ]
    created = client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Demo Branch 3"}
    )
    assert created.status_code == 201
    assert created.json()["name"] == "DEMO BRANCH 3"
    duplicate = client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Duplicate"}
    )
    assert duplicate.status_code == 409


def test_account_opening_uses_selected_database_branch(dashboard_client):
    client, actor, session = dashboard_client

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
                "email": "Mira.Kapoor@Example.com",
                "address_line1": "42 Green Road",
                "address_city": "New Delhi",
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
    customer = session.get(Customer, account.customer_id)
    assert customer.first_name == "MIRA"
    assert customer.last_name == "KAPOOR"
    assert customer.country == "INDIA"
    assert customer.state == "DELHI"
    assert customer.email == "mira.kapoor@example.com"
    assert customer.address_line1 == "42 GREEN ROAD"
    assert customer.address_city == "NEW DELHI"
    event = (
        session.query(AuditEvent)
        .filter_by(actor_id=actor.id, action="account.open")
        .one()
    )
    assert event.metadata_json == {
        "account_number": account.account_number,
        "account_type": "SAVINGS",
        "branch_ifsc": "SHIV0000002",
        "opening_deposit_minor": 200_000,
        "kyc_status": "PENDING",
    }


def test_pending_kyc_blocks_account_operations(dashboard_client):
    client, _, session = dashboard_client
    account = session.query(Account).filter_by(account_number="1000000001").one()
    customer = session.get(Customer, account.customer_id)
    customer.kyc_status = "PENDING"
    starting_balance = account.balance_minor
    session.commit()

    response = client.post(
        "/accounts/1000000001/deposits",
        headers={"Idempotency-Key": "pending-kyc-deposit"},
        json={"amount": "10.00"},
    )

    assert response.status_code == 400
    assert "KYC is pending" in response.json()["detail"]
    session.refresh(account)
    assert account.balance_minor == starting_balance


def test_deposit_memo_is_saved_uppercase_and_search_is_case_insensitive(dashboard_client):
    client, actor, session = dashboard_client

    deposit = client.post(
        "/accounts/1000000001/deposits",
        headers={"Idempotency-Key": "uppercase-memo-test"},
        json={"amount": "10.00", "memo": "counter deposit"},
    )
    search = client.get("/accounts", params={"q": "asha"})

    assert deposit.status_code == 200
    transaction = (
        session.query(LedgerTransaction)
        .filter_by(actor_id=actor.id, kind="DEPOSIT")
        .one()
    )
    assert transaction.memo == "COUNTER DEPOSIT"
    event = (
        session.query(AuditEvent)
        .filter_by(actor_id=actor.id, action="deposit")
        .one()
    )
    assert event.metadata_json["memo"] == "COUNTER DEPOSIT"
    assert search.status_code == 200
    assert [item["account_number"] for item in search.json()["items"]] == [
        "1000000001"
    ]


def test_rejected_kyc_is_terminal_and_profile_is_locked(dashboard_client):
    client, _, session = dashboard_client
    account = session.query(Account).filter_by(account_number="1000000001").one()
    customer = session.get(Customer, account.customer_id)

    rejected = client.patch(
        f"/customers/{customer.id}/kyc",
        json={"kyc_status": "REJECTED"},
    )
    attempt_reapproval = client.patch(
        f"/customers/{customer.id}/kyc",
        json={"kyc_status": "VERIFIED"},
    )
    attempt_profile_edit = client.patch(
        f"/customers/{customer.id}/profile",
        json={"phone": "7777777777"},
    )

    assert rejected.status_code == 200
    assert attempt_reapproval.status_code == 409
    assert attempt_profile_edit.status_code == 409
    session.refresh(customer)
    assert customer.kyc_status == "REJECTED"


def test_staff_account_allows_only_one_active_device_session(dashboard_client):
    client, actor, session = dashboard_client
    actor.password_hash = hash_password("correct horse battery")
    session.commit()
    first_session_id = str(uuid.uuid4())
    second_session_id = str(uuid.uuid4())
    credentials = {"username": actor.username, "password": "correct horse battery"}

    first_login = client.post(
        "/auth/login",
        headers={"X-Banking-Session": first_session_id},
        json=credentials,
    )
    blocked_login = client.post(
        "/auth/login",
        headers={"X-Banking-Session": second_session_id},
        json=credentials,
    )

    assert first_login.status_code == 200
    assert blocked_login.status_code == 409
    signed_out = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first_login.json()['access_token']}"},
    )
    assert signed_out.status_code == 200
    second_login = client.post(
        "/auth/login",
        headers={"X-Banking-Session": second_session_id},
        json=credentials,
    )
    assert second_login.status_code == 200


def test_teller_cannot_create_branches(dashboard_client):
    client, actor, _ = dashboard_client
    actor.role = "TELLER"

    response = client.post(
        "/branches", json={"ifsc": "SHIV0000003", "name": "Restricted Branch"}
    )

    assert response.status_code == 403


def test_savings_daily_cap_is_shared_by_withdrawals_and_transfers(dashboard_client):
    client, actor, session = dashboard_client
    sender = session.query(Account).filter_by(account_number="1000000001").one()
    receiver = session.query(Account).filter_by(account_number="1000000002").one()
    sender.balance_minor = 60_000_000
    receiver.status = "ACTIVE"
    session.add_all(
        [
            LedgerAccount(
                code=f"TEST:{sender.account_number}",
                account_type="CUSTOMER_DEPOSIT",
                account_id=sender.id,
            ),
            LedgerAccount(
                code=f"TEST:{receiver.account_number}",
                account_type="CUSTOMER_DEPOSIT",
                account_id=receiver.id,
            ),
        ]
    )
    session.commit()

    withdrawal = client.post(
        "/accounts/1000000001/withdrawals",
        headers={"Idempotency-Key": "daily-limit-withdrawal"},
        json={"amount": "300000.00"},
    )
    transfer = client.post(
        "/transfers",
        headers={"Idempotency-Key": "daily-limit-transfer"},
        json={
            "sender_account": "1000000001",
            "receiver_account": "1000000002",
            "amount": "200000.00",
        },
    )
    over_limit = client.post(
        "/accounts/1000000001/withdrawals",
        headers={"Idempotency-Key": "daily-limit-over"},
        json={"amount": "0.01"},
    )

    assert withdrawal.status_code == 200, withdrawal.json()
    assert transfer.status_code == 200
    assert over_limit.status_code == 400
    assert "500000.00" in over_limit.json()["detail"]
    limit = client.get("/accounts/1000000001")
    assert limit.json()["daily_withdrawal_limit"] == "500000.00"
    assert limit.json()["daily_withdrawn_today"] == "500000.00"
    assert limit.json()["daily_withdrawal_remaining"] == "0.00"
    transfer_audit = (
        session.query(AuditEvent)
        .filter_by(actor_id=actor.id, action="account.transfer")
        .one()
    )
    assert transfer_audit.metadata_json == {
        "sender": "1000000001",
        "receiver": "1000000002",
        "amount_minor": 20_000_000,
        "transaction_id": transfer.json()["transaction_id"],
        "memo": "",
    }
    withdrawal_audit = (
        session.query(AuditEvent)
        .filter_by(actor_id=actor.id, action="withdrawal")
        .one()
    )
    assert withdrawal_audit.metadata_json["account_number"] == "1000000001"
    assert withdrawal_audit.metadata_json["amount_minor"] == 30_000_000


def test_audit_logs_endpoint(dashboard_client):
    client, _, _ = dashboard_client
    response = client.get("/admin/audit-logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_staff_can_view_only_their_activity_while_admin_can_view_all(dashboard_client):
    client, actor, session = dashboard_client
    other_staff = StaffUser(
        id=uuid.uuid4(),
        username="teller",
        full_name="Demo Teller",
        role="TELLER",
        password_hash="unused",
    )
    session.add_all(
        [
            other_staff,
            AuditEvent(
                actor_id=actor.id,
                action="account.deposit",
                entity_type="account",
                entity_id="own-account",
            ),
            AuditEvent(
                actor_id=other_staff.id,
                action="account.transfer",
                entity_type="ledger_transaction",
                entity_id="other-transfer",
                metadata_json={"sender": "1000000001", "receiver": "1000000002"},
            ),
        ]
    )
    session.commit()

    mine = client.get("/staff/audit-logs")
    actor.role = "TELLER"
    forbidden_all = client.get("/admin/audit-logs")
    actor.role = "ADMIN"
    all_activity = client.get("/admin/audit-logs")

    assert mine.status_code == 200
    assert [event["action"] for event in mine.json()] == ["account.deposit"]
    assert forbidden_all.status_code == 403
    assert all_activity.status_code == 200
    assert {event["action"] for event in all_activity.json()} == {
        "account.deposit",
        "account.transfer",
    }


def test_statement_json_endpoint(dashboard_client):
    client, _, _ = dashboard_client
    response = client.get("/accounts/1000000001/statement")
    assert response.status_code == 200
    data = response.json()
    assert data["account_number"] == "1000000001"
    assert "entries" in data
    assert "current_balance" in data
