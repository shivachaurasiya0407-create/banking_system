import logging
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from banking_api.auth import (
    authenticate_staff,
    create_access_token,
    get_db,
    get_settings,
    require_roles,
)
from banking_api.models import (
    Account,
    AuditEvent,
    Customer,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    StaffUser,
)
from banking_api.schemas import (
    AccountOpenRequest,
    AccountStatusRequest,
    LoginRequest,
    MoneyRequest,
    StaffCreateRequest,
    StaffPasswordResetRequest,
    TokenResponse,
    TransferRequest,
)
from banking_api.security import hash_password
from banking_api.service import BankingError, BankingService, IdempotencyConflict
from banking_api.settings import Settings


logger = logging.getLogger("banking_api")
app = FastAPI(
    title="Banking System Prototype API",
    version="1.0.0",
    description=(
        "Educational banking prototype. Not approved for real customer data or funds."
    ),
)


def _service(session, settings):
    return BankingService(session, settings)


def _operation_response(result):
    return {
        "transaction_id": str(result.transaction_id),
        "account_numbers": list(result.account_numbers),
        "balances": [f"{Decimal(balance) / 100:.2f}" for balance in result.balances_minor],
        "replayed": result.replayed,
    }


@app.exception_handler(BankingError)
async def banking_error_handler(request: Request, error: BankingError):
    logger.debug("Handled a banking validation error for %s.", request.method)
    if isinstance(error, IdempotencyConflict):
        return JSONResponse(
            status_code=409, content={"detail": str(error)}
        )
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, error: IntegrityError):
    logger.warning(
        "Database constraint rejected a %s request (%s).",
        request.method,
        type(error).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Request conflicts with existing banking data."},
    )


@app.get("/healthz", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
def readiness(session: Annotated[Session, Depends(get_db)]):
    from sqlalchemy import text

    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post("/auth/login", response_model=TokenResponse, tags=["authentication"])
def login(
    body: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    staff = authenticate_staff(session, body.username, body.password, settings)
    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or account temporarily unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(staff, settings)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_minutes * 60,
        role=staff.role,
    )


@app.post("/staff", status_code=201, tags=["staff"])
def create_staff(
    body: StaffCreateRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
):
    staff = StaffUser(
        id=uuid.uuid4(),
        username=body.username.strip().casefold(),
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(body.password),
    )
    session.add(staff)
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="staff.create",
            entity_type="staff_user",
            entity_id=str(staff.id),
        )
    )
    session.commit()
    return {"id": str(staff.id), "username": staff.username, "role": staff.role}


@app.get("/staff", tags=["staff"])
def list_staff(
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    staff_members = session.scalars(
        select(StaffUser)
        .order_by(StaffUser.created_at, StaffUser.id)
        .limit(limit)
        .offset(offset)
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="staff.list",
            entity_type="staff_user",
            entity_id="collection",
        )
    )
    session.commit()
    return [
        {
            "id": str(staff.id),
            "username": staff.username,
            "full_name": staff.full_name,
            "role": staff.role,
            "active": staff.active,
            "created_at": staff.created_at,
        }
        for staff in staff_members
    ]


@app.post("/staff/{staff_id}/password-reset", tags=["staff"])
def reset_staff_password(
    staff_id: uuid.UUID,
    body: StaffPasswordResetRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
):
    target = session.scalar(
        select(StaffUser).where(StaffUser.id == staff_id).with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Staff user not found.")
    target.password_hash = hash_password(body.password)
    target.failed_login_attempts = 0
    target.locked_until = None
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="staff.password_reset",
            entity_type="staff_user",
            entity_id=str(target.id),
        )
    )
    session.commit()
    return {"status": "password reset"}


@app.post("/accounts", status_code=201, tags=["accounts"])
def open_account(
    body: AccountOpenRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).open_account(
        actor.id,
        idempotency_key,
        body.customer.model_dump(),
        body.opening_deposit,
    )
    return _operation_response(result)


@app.get("/accounts/{account_number}", tags=["accounts"])
def account_details(
    account_number: str,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
):
    account = session.scalar(
        select(Account).where(Account.account_number == account_number)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    customer = session.get(Customer, account.customer_id)
    if customer is None:
        raise HTTPException(status_code=500, detail="Account owner record is missing.")
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.read",
            entity_type="account",
            entity_id=str(account.id),
        )
    )
    session.commit()
    return {
        "account_number": account.account_number,
        "ifsc": account.ifsc,
        "status": account.status,
        "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
        "customer": {
            "id": str(customer.id),
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "phone": customer.phone,
            "age": customer.age,
            "country": customer.country,
            "state": customer.state,
        },
    }


@app.get("/accounts/{account_number}/balance", tags=["accounts"])
def balance(
    account_number: str,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
):
    account = session.scalar(
        select(Account).where(Account.account_number == account_number)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.balance_read",
            entity_type="account",
            entity_id=str(account.id),
        )
    )
    session.commit()
    return {"account_number": account.account_number, "balance": f"{Decimal(account.balance_minor) / 100:.2f}", "status": account.status}


@app.get("/accounts/{account_number}/transactions", tags=["accounts"])
def transactions(
    account_number: str,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    account = session.scalar(
        select(Account).where(Account.account_number == account_number)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    rows = session.execute(
        select(LedgerEntry, LedgerTransaction)
        .join(LedgerTransaction, LedgerEntry.transaction_id == LedgerTransaction.id)
        .join(LedgerAccount, LedgerEntry.ledger_account_id == LedgerAccount.id)
        .where(LedgerAccount.account_id == account.id)
        .order_by(LedgerTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.transactions_read",
            entity_type="account",
            entity_id=str(account.id),
        )
    )
    session.commit()
    return [
        {
            "transaction_id": str(transaction.id),
            "type": transaction.kind,
            "date": transaction.created_at.isoformat(),
            "credit": f"{max(-entry.amount_minor, 0) / 100:.2f}",
            "debit": f"{max(entry.amount_minor, 0) / 100:.2f}",
            "status": transaction.status,
        }
        for entry, transaction in rows
    ]


@app.post("/accounts/{account_number}/deposits", tags=["operations"])
def deposit(
    account_number: str,
    body: MoneyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).change_balance(
        actor.id, idempotency_key, account_number, "DEPOSIT", body.amount
    )
    return _operation_response(result)


@app.post("/accounts/{account_number}/withdrawals", tags=["operations"])
def withdrawal(
    account_number: str,
    body: MoneyRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).change_balance(
        actor.id, idempotency_key, account_number, "WITHDRAWAL", body.amount
    )
    return _operation_response(result)


@app.post("/transfers", tags=["operations"])
def transfer(
    body: TransferRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).transfer(
        actor.id,
        idempotency_key,
        body.sender_account,
        body.receiver_account,
        body.amount,
    )
    return _operation_response(result)


@app.post("/accounts/{account_number}/status", tags=["operations"])
def set_account_status(
    account_number: str,
    body: AccountStatusRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).set_account_status(
        actor.id, idempotency_key, account_number, body.status
    )
    return _operation_response(result)
