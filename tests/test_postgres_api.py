import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from banking_api.app import app
from banking_api.auth import create_access_token, get_db, get_settings
from banking_api.models import (
    Account,
    AuditEvent,
    Base,
    Branch,
    Customer,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    StaffUser,
)
from banking_api.security import hash_password
from banking_api.settings import Settings


class PostgresApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(
            bind=cls.engine, autoflush=False, expire_on_commit=False
        )
        cls.settings = Settings(
            database_url="postgresql+psycopg://test:test@localhost/test",
            jwt_secret="test-secret-that-is-at-least-32-bytes-long",
            pii_hmac_key="test-pii-key-that-is-at-least-32-bytes-long",
            jwt_issuer="banking-tests",
            access_token_minutes=15,
            login_max_attempts=5,
            login_lockout_minutes=15,
        )
        with patch("banking_api.security.PBKDF2_ITERATIONS", 1_000):
            cls.password_hash = hash_password("BankingTest123")
        def override_db():
            with Session(cls.engine) as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_settings] = lambda: cls.settings
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            session.add(
                Branch(ifsc="SHIV0000001", name="Main Branch", next_sequence=1)
            )
            session.add(
                LedgerAccount(
                    code="SYSTEM:CASH_CLEARING",
                    account_type="CASH_CLEARING",
                )
            )
            for role in ("ADMIN", "TELLER", "AUDITOR"):
                session.add(
                    StaffUser(
                        id=uuid.uuid5(uuid.NAMESPACE_DNS, role.lower()),
                        username=role.lower(),
                        full_name=f"Test {role}",
                        role=role,
                        password_hash=self.password_hash,
                    )
                )
            session.commit()
            self.tokens = {
                staff.role: create_access_token(staff, self.settings)
                for staff in session.scalars(select(StaffUser)).all()
            }
        self.admin_headers = {
            "Authorization": f"Bearer {self.tokens['ADMIN']}",
            "Idempotency-Key": str(uuid.uuid4()),
        }

    def _open_account(self, identity, idempotency_key=None):
        headers = {
            "Authorization": f"Bearer {self.tokens['TELLER']}",
            "Idempotency-Key": idempotency_key or str(uuid.uuid4()),
        }
        response = self.client.post(
            "/accounts",
            headers=headers,
            json={
                "customer": {
                    "first_name": "Person",
                    "last_name": "Test",
                    "phone": "0123456789",
                    "age": 30,
                    "country": "india",
                    "state": "delhi",
                    "identity_number": identity,
                },
                "opening_deposit": "5000.00",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_opening_deposit_and_repeated_request_are_idempotent(self):
        key = str(uuid.uuid4())
        first = self._open_account("111122223333", key)
        second = self._open_account("111122223333", key)
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(first["account_numbers"], second["account_numbers"])
        self.assertEqual(first["balances"], ["5000.00"])
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(func.count(Account.id))), 1)
            txn = session.scalar(select(LedgerTransaction))
            postings = session.scalars(
                select(LedgerEntry).where(LedgerEntry.transaction_id == txn.id)
            ).all()
            self.assertEqual(len(postings), 2)
            self.assertEqual(sum(item.amount_minor for item in postings), 0)

    def test_deposit_withdrawal_transfer_and_transaction_history(self):
        first = self._open_account("111122223333")
        second = self._open_account("444455556666")
        sender, receiver = first["account_numbers"][0], second["account_numbers"][0]
        headers = {
            "Authorization": f"Bearer {self.tokens['TELLER']}",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        deposit = self.client.post(
            f"/accounts/{sender}/deposits",
            headers=headers,
            json={"amount": "10.25"},
        )
        self.assertEqual(deposit.status_code, 200, deposit.text)
        withdrawal = self.client.post(
            f"/accounts/{sender}/withdrawals",
            headers={"Authorization": headers["Authorization"], "Idempotency-Key": str(uuid.uuid4())},
            json={"amount": "5.25"},
        )
        self.assertEqual(withdrawal.status_code, 200, withdrawal.text)
        transfer = self.client.post(
            "/transfers",
            headers={"Authorization": headers["Authorization"], "Idempotency-Key": str(uuid.uuid4())},
            json={
                "sender_account": sender,
                "receiver_account": receiver,
                "amount": "100.00",
            },
        )
        self.assertEqual(transfer.status_code, 200, transfer.text)
        self.assertEqual(transfer.json()["balances"], ["4905.00", "5100.00"])
        balance = self.client.get(
            f"/accounts/{sender}/balance",
            headers={"Authorization": headers["Authorization"]},
        )
        self.assertEqual(balance.status_code, 200)
        self.assertEqual(balance.json()["balance"], "4905.00")
        history = self.client.get(
            f"/accounts/{sender}/transactions",
            headers={"Authorization": headers["Authorization"]},
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()), 4)

    def test_idempotency_key_cannot_be_reused_for_different_payload(self):
        account = self._open_account("111122223333")
        key = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {self.tokens['TELLER']}",
            "Idempotency-Key": key,
        }
        first = self.client.post(
            f"/accounts/{account['account_numbers'][0]}/deposits",
            headers=headers,
            json={"amount": "1.00"},
        )
        second = self.client.post(
            f"/accounts/{account['account_numbers'][0]}/deposits",
            headers=headers,
            json={"amount": "2.00"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_auditor_cannot_mutate_balances(self):
        account = self._open_account("111122223333")
        response = self.client.post(
            f"/accounts/{account['account_numbers'][0]}/deposits",
            headers={
                "Authorization": f"Bearer {self.tokens['AUDITOR']}",
                "Idempotency-Key": str(uuid.uuid4()),
            },
            json={"amount": "1.00"},
        )
        self.assertEqual(response.status_code, 403)

    def test_account_status_is_admin_only_and_audited(self):
        account = self._open_account("111122223333")
        response = self.client.post(
            f"/accounts/{account['account_numbers'][0]}/status",
            headers=self.admin_headers,
            json={"status": "FROZEN"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            self.client.get(
                f"/accounts/{account['account_numbers'][0]}/balance",
                headers={"Authorization": f"Bearer {self.tokens['TELLER']}"},
            ).json()["status"],
            "FROZEN",
        )
        with Session(self.engine) as session:
            self.assertGreater(
                session.scalar(select(func.count(AuditEvent.id))), 0
            )

    def test_private_routes_require_authentication(self):
        response = self.client.get("/accounts/1234567890/balance")
        self.assertEqual(response.status_code, 401)

    def test_staff_login_returns_access_token(self):
        response = self.client.post(
            "/auth/login",
            json={"username": "teller", "password": "BankingTest123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["role"], "TELLER")
        self.assertGreater(response.json()["expires_in"], 0)

    def test_admin_can_add_staff_and_staff_can_open_account(self):
        with patch("banking_api.security.PBKDF2_ITERATIONS", 1_000):
            new_staff_hash = hash_password("StrongEmployee123")
        with patch("banking_api.app.hash_password", return_value=new_staff_hash):
            created = self.client.post(
                "/staff",
                headers=self.admin_headers,
                json={
                    "username": "new.teller",
                    "full_name": "New Teller",
                    "role": "TELLER",
                    "password": "StrongEmployee123",
                },
            )
        self.assertEqual(created.status_code, 201, created.text)

        staff_list = self.client.get("/staff", headers=self.admin_headers)
        self.assertEqual(staff_list.status_code, 200, staff_list.text)
        new_staff = next(
            staff for staff in staff_list.json()
            if staff["username"] == "new.teller"
        )
        self.assertEqual(new_staff["full_name"], "New Teller")
        self.assertEqual(new_staff["role"], "TELLER")
        self.assertNotIn("password_hash", new_staff)

        login = self.client.post(
            "/auth/login",
            json={"username": "new.teller", "password": "StrongEmployee123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        teller_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        account = self.client.post(
            "/accounts",
            headers=teller_headers,
            json={
                "customer": {
                    "first_name": "New",
                    "last_name": "Customer",
                    "phone": "0123456789",
                    "age": 30,
                    "country": "India",
                    "state": "Delhi",
                    "identity_number": "987654321012",
                },
                "opening_deposit": "2000.00",
            },
        )
        self.assertEqual(account.status_code, 201, account.text)
        self.assertEqual(account.json()["balances"], ["2000.00"])

    def test_customer_endpoint_does_not_persist_raw_identity_number(self):
        self._open_account("111122223333")
        with Session(self.engine) as session:
            customer = session.scalar(select(Customer))
            self.assertNotIn("111122223333", customer.identity_fingerprint)


if __name__ == "__main__":
    unittest.main()
