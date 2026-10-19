import csv
import io
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from banking_api.auth import (
    authenticate_staff,
    create_access_token,
    get_current_staff,
    get_db,
    get_settings,
    require_roles,
)
from banking_api.locations import INDIA_STATES
from banking_api.models import (
    Account,
    AuditEvent,
    Branch,
    Customer,
    LedgerTransaction,
    StaffUser,
)
from banking_api.schemas import (
    AccountOpenRequest,
    AccountStatusRequest,
    BranchCreateRequest,
    LoginRequest,
    MoneyRequest,
    StaffCreateRequest,
    StaffPasswordResetRequest,
    StaffUpdateRequest,
    TokenResponse,
    TransactionReversalRequest,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
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


@app.middleware("http")
async def request_correlation(request: Request, call_next):
    request_id = uuid.uuid4().hex
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Request failed.",
            extra={"request_id": request_id, "method": request.method},
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "Request completed.",
        extra={
            "request_id": request_id,
            "method": request.method,
            "status_code": response.status_code,
        },
    )
    return response


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


@app.get("/auth/me", tags=["authentication"])
def current_staff(actor: Annotated[StaffUser, Depends(get_current_staff)]):
    return {
        "id": str(actor.id),
        "username": actor.username,
        "full_name": actor.full_name,
        "role": actor.role,
    }


@app.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(
    actor: Annotated[StaffUser, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
):
    counts = dict(
        session.execute(
            select(Account.status, func.count(Account.id)).group_by(Account.status)
        ).all()
    )
    total_balance_minor = session.scalar(
        select(func.coalesce(func.sum(Account.balance_minor), 0))
    )
    transaction_count = session.scalar(
        select(func.count()).select_from(LedgerTransaction)
    )
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="dashboard.summary_read",
            entity_type="dashboard",
            entity_id="summary",
        )
    )
    session.commit()
    return {
        "accounts": {
            "total": sum(counts.values()),
            "active": counts.get("ACTIVE", 0),
            "frozen": counts.get("FROZEN", 0),
            "closed": counts.get("CLOSED", 0),
        },
        "total_balance": f"{Decimal(total_balance_minor or 0) / 100:.2f}",
        "transactions": transaction_count,
    }


@app.get("/branches", tags=["branches"])
def list_branches(
    actor: Annotated[StaffUser, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
):
    branches = [
        {"ifsc": branch.ifsc, "name": branch.name}
        for branch in session.scalars(select(Branch).order_by(Branch.name, Branch.ifsc))
    ]
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="branch.list",
            entity_type="branch",
            entity_id="collection",
        )
    )
    session.commit()
    return branches


@app.get("/metadata/india-states", tags=["metadata"])
def list_india_states():
    return list(INDIA_STATES)


@app.post("/branches", status_code=201, tags=["branches"])
def create_branch(
    body: BranchCreateRequest,
    actor: Annotated[StaffUser, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
):
    if session.get(Branch, body.ifsc) is not None:
        raise HTTPException(status_code=409, detail="A branch with this IFSC already exists.")
    branch = Branch(ifsc=body.ifsc, name=body.name.strip(), next_sequence=1)
    session.add(branch)
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="branch.create",
            entity_type="branch",
            entity_id=branch.ifsc,
        )
    )
    session.commit()
    return {"ifsc": branch.ifsc, "name": branch.name}


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
    target.token_version += 1
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


@app.patch("/staff/{staff_id}", tags=["staff"])
def update_staff(
    staff_id: uuid.UUID,
    body: StaffUpdateRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
):
    target = session.scalar(
        select(StaffUser).where(StaffUser.id == staff_id).with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Staff user not found.")
    if target.id == actor.id and body.active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    removes_admin = target.role == "ADMIN" and (
        body.role not in (None, "ADMIN") or body.active is False
    )
    if removes_admin:
        active_admins = session.scalar(
            select(func.count()).select_from(StaffUser).where(
                StaffUser.role == "ADMIN", StaffUser.active.is_(True)
            )
        )
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be removed.")
    previous = {"role": target.role, "active": target.active}
    if body.role is not None:
        target.role = body.role
    if body.active is not None:
        target.active = body.active
    if target.role != previous["role"] or target.active != previous["active"]:
        target.token_version += 1
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="staff.update",
            entity_type="staff_user",
            entity_id=str(target.id),
            metadata_json={
                "previous": previous,
                "role": target.role,
                "active": target.active,
            },
        )
    )
    session.commit()
    return {
        "id": str(target.id),
        "username": target.username,
        "role": target.role,
        "active": target.active,
    }


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
        body.branch_ifsc,
    )
    return _operation_response(result)


@app.get("/accounts", tags=["accounts"])
def search_accounts(
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    statement = select(Account, Customer).join(Customer, Account.customer_id == Customer.id)
    if q:
        search = q.strip()
        if not search:
            raise HTTPException(status_code=422, detail="Search query cannot be blank.")
        statement = statement.where(
            or_(
                Account.account_number.startswith(search, autoescape=True),
                Customer.first_name.startswith(search, autoescape=True),
                Customer.last_name.startswith(search, autoescape=True),
            )
        )
    results = session.execute(
        statement.order_by(Account.account_number).limit(limit).offset(offset)
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.search",
            entity_type="account",
            entity_id="collection",
            metadata_json={"query_present": bool(q), "result_count": len(results)},
        )
    )
    session.commit()
    return {
        "items": [
            {
                "account_number": account.account_number,
                "ifsc": account.ifsc,
                "status": account.status,
                "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
                "customer_name": f"{customer.first_name} {customer.last_name}",
            }
            for account, customer in results
        ],
        "limit": limit,
        "offset": offset,
    }


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
    customer_response = {
        "id": str(customer.id),
        "first_name": customer.first_name,
        "last_name": customer.last_name,
    }
    if actor.role in {"ADMIN", "TELLER"}:
        customer_response["phone"] = customer.phone
    return {
        "account_number": account.account_number,
        "ifsc": account.ifsc,
        "status": account.status,
        "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
        "customer": customer_response,
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
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    kind: Annotated[str | None, Query(pattern=r"^(OPENING_DEPOSIT|DEPOSIT|WITHDRAWAL|TRANSFER|ACCOUNT_STATUS)$")] = None,
):
    account = session.scalar(
        select(Account).where(Account.account_number == account_number)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must not be after end_at.")
    _, rows = _service(session, settings).get_transactions(
        account_number, limit, offset, start_at, end_at, kind
    )
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


@app.get("/accounts/{account_number}/statement.csv", tags=["accounts"])
def export_statement(
    account_number: str,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    kind: Annotated[str | None, Query(pattern=r"^(OPENING_DEPOSIT|DEPOSIT|WITHDRAWAL|TRANSFER|ACCOUNT_STATUS)$")] = None,
):
    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must not be after end_at.")
    account, rows = _service(session, settings).get_statement(
        account_number,
        limit=limit,
        offset=offset,
        start_at=start_at,
        end_at=end_at,
        kind=kind,
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow((
        "account_number", "transaction_id", "date", "type", "credit", "debit",
        "running_balance", "status",
    ))
    for row in rows:
        writer.writerow((
            account.account_number,
            str(row.transaction_id),
            row.created_at.isoformat(),
            row.kind,
            f"{max(-row.amount_minor, 0) / 100:.2f}",
            f"{max(row.amount_minor, 0) / 100:.2f}",
            f"{row.balance_minor / 100:.2f}",
            row.status,
        ))
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.statement_export",
            entity_type="account",
            entity_id=str(account.id),
            metadata_json={"row_count": len(rows)},
        )
    )
    session.commit()
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="statement-{account_number}.csv"'},
    )


@app.get("/admin/reconciliation", tags=["operations"])
def reconciliation(
    actor: Annotated[object, Depends(require_roles("ADMIN", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    report = _service(session, settings).reconcile_ledger()
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="ledger.reconciliation",
            entity_type="ledger",
            entity_id="all",
            metadata_json={"balanced": report["balanced"], "discrepancy_count": len(report["discrepancies"])},
        )
    )
    session.commit()
    return report


@app.post("/transactions/{transaction_id}/reversals", tags=["operations"])
def reverse_transaction(
    transaction_id: uuid.UUID,
    body: TransactionReversalRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = _service(session, settings).reverse_transaction(
        actor.id, idempotency_key, transaction_id, body.reason
    )
    return _operation_response(result)


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
