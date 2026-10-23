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
    FixedDeposit,
    Loan,
    LoanRepayment,
    LedgerTransaction,
    NotificationLog,
    StaffUser,
)
from banking_api.schemas import (
    AccountOpenRequest,
    AccountStatusRequest,
    BranchCreateRequest,
    CustomerKycRequest,
    CustomerUpdateRequest,
    FixedDepositCloseRequest,
    FixedDepositOpenRequest,
    LoanActionRequest,
    LoanApplicationRequest,
    LoanRepaymentRequest,
    LoginRequest,
    MoneyRequest,
    StaffChangePasswordRequest,
    StaffCreateRequest,
    StaffPasswordResetRequest,
    StaffUpdateRequest,
    TokenResponse,
    TransactionReversalRequest,
    TransferRequest,
)
from banking_api.security import hash_password, verify_password
from banking_api.service import BankingError, BankingService, IdempotencyConflict
from banking_api.settings import Settings

logger = logging.getLogger("banking_api")
app = FastAPI(
    title="SHIVA Banking System API",
    version="2.0.0",
    description=(
        "Full-featured banking system with accounts, loans, fixed deposits, "
        "interest engine, KYC, audit trail, and notification log."
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
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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


# ─── System ───────────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
def readiness(session: Annotated[Session, Depends(get_db)]):
    from sqlalchemy import text
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


# ─── Authentication ───────────────────────────────────────────────────────────

@app.get("/auth/me", tags=["authentication"])
def current_staff(actor: Annotated[StaffUser, Depends(get_current_staff)]):
    return {
        "id": str(actor.id),
        "username": actor.username,
        "full_name": actor.full_name,
        "role": actor.role,
    }


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


@app.post("/auth/change-password", tags=["authentication"])
def change_password(
    body: StaffChangePasswordRequest,
    actor: Annotated[StaffUser, Depends(get_current_staff)],
    session: Annotated[Session, Depends(get_db)],
):
    target = session.scalar(
        select(StaffUser).where(StaffUser.id == actor.id).with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Staff user not found.")
    if not verify_password(body.current_password, target.password_hash):
        session.add(
            AuditEvent(
                actor_id=target.id,
                action="auth.change_password_failed",
                entity_type="staff_user",
                entity_id=str(target.id),
            )
        )
        session.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    target.password_hash = hash_password(body.new_password)
    target.token_version += 1
    session.add(
        AuditEvent(
            actor_id=target.id,
            action="auth.password_changed",
            entity_type="staff_user",
            entity_id=str(target.id),
        )
    )
    session.commit()
    return {"status": "password changed successfully"}


# ─── Dashboard ────────────────────────────────────────────────────────────────

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
    # Loan summary
    loan_counts = dict(
        session.execute(
            select(Loan.status, func.count(Loan.id)).group_by(Loan.status)
        ).all()
    )
    active_loans_outstanding = session.scalar(
        select(func.coalesce(func.sum(Loan.outstanding_minor), 0)).where(
            Loan.status == "ACTIVE"
        )
    ) or 0
    # FD summary
    active_fd_count = session.scalar(
        select(func.count(FixedDeposit.id)).where(FixedDeposit.status == "ACTIVE")
    ) or 0
    active_fd_value = session.scalar(
        select(func.coalesce(func.sum(FixedDeposit.principal_minor), 0)).where(
            FixedDeposit.status == "ACTIVE"
        )
    ) or 0
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
        "loans": {
            "active": loan_counts.get("ACTIVE", 0),
            "applied": loan_counts.get("APPLIED", 0),
            "approved": loan_counts.get("APPROVED", 0),
            "outstanding": f"{Decimal(active_loans_outstanding) / 100:.2f}",
        },
        "fixed_deposits": {
            "active": active_fd_count,
            "total_value": f"{Decimal(active_fd_value) / 100:.2f}",
        },
    }


# ─── Branches ─────────────────────────────────────────────────────────────────

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


# ─── Staff ────────────────────────────────────────────────────────────────────

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


# ─── Accounts ─────────────────────────────────────────────────────────────────

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
        body.account_type,
    )
    return _operation_response(result)


@app.get("/accounts", tags=["accounts"])
def search_accounts(
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    account_type: Annotated[str | None, Query()] = None,
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
    if status_filter and status_filter in {"ACTIVE", "FROZEN", "CLOSED"}:
        statement = statement.where(Account.status == status_filter)
    if account_type and account_type in {"SAVINGS", "CURRENT", "SALARY"}:
        statement = statement.where(Account.account_type == account_type)
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
                "account_type": account.account_type,
                "ifsc": account.ifsc,
                "status": account.status,
                "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "interest_rate": str(account.interest_rate_annual),
                "kyc_status": customer.kyc_status,
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
        "kyc_status": customer.kyc_status,
        "address_city": customer.address_city,
    }
    if actor.role in {"ADMIN", "TELLER"}:
        customer_response["phone"] = customer.phone
        customer_response["email"] = customer.email
        customer_response["address_line1"] = customer.address_line1
        customer_response["address_pin"] = customer.address_pin
    return {
        "account_number": account.account_number,
        "account_type": account.account_type,
        "ifsc": account.ifsc,
        "status": account.status,
        "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
        "interest_rate_annual": str(account.interest_rate_annual),
        "daily_withdrawal_limit": (
            f"{Decimal(account.daily_withdrawal_limit_minor) / 100:.2f}"
            if account.daily_withdrawal_limit_minor > 0
            else "No limit"
        ),
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
    return {
        "account_number": account.account_number,
        "account_type": account.account_type,
        "balance": f"{Decimal(account.balance_minor) / 100:.2f}",
        "status": account.status,
    }


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
    kind: Annotated[str | None, Query(pattern=r"^(OPENING_DEPOSIT|DEPOSIT|WITHDRAWAL|TRANSFER|ACCOUNT_STATUS|INTEREST|LOAN_DISBURSEMENT|LOAN_REPAYMENT|FD_OPEN|FD_MATURITY|FD_PREMATURE_CLOSURE)$")] = None,
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
            "memo": transaction.memo or "",
        }
        for entry, transaction in rows
    ]


@app.get("/accounts/{account_number}/statement", tags=["accounts"])
def account_statement(
    account_number: str,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    kind: Annotated[str | None, Query(pattern=r"^(OPENING_DEPOSIT|DEPOSIT|WITHDRAWAL|TRANSFER|ACCOUNT_STATUS|INTEREST|LOAN_DISBURSEMENT|LOAN_REPAYMENT|FD_OPEN|FD_MATURITY|FD_PREMATURE_CLOSURE)$")] = None,
):
    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must not be after end_at.")
    account, rows = _service(session, settings).get_statement(
        account_number, limit=limit, offset=offset, start_at=start_at, end_at=end_at, kind=kind,
    )
    customer = session.get(Customer, account.customer_id)
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="account.statement_read",
            entity_type="account",
            entity_id=str(account.id),
            metadata_json={"row_count": len(rows)},
        )
    )
    session.commit()
    entries = [
        {
            "transaction_id": str(row.transaction_id),
            "date": row.created_at.isoformat(),
            "type": row.kind,
            "credit": f"{max(-row.amount_minor, 0) / 100:.2f}",
            "debit": f"{max(row.amount_minor, 0) / 100:.2f}",
            "running_balance": f"{row.balance_minor / 100:.2f}",
            "status": row.status,
            "memo": getattr(row, "memo", "") or "",
        }
        for row in rows
    ]
    total_credit = sum(max(-row.amount_minor, 0) for row in rows) / 100
    total_debit = sum(max(row.amount_minor, 0) for row in rows) / 100
    return {
        "account_number": account.account_number,
        "account_type": account.account_type,
        "ifsc": account.ifsc,
        "status": account.status,
        "current_balance": f"{Decimal(account.balance_minor) / 100:.2f}",
        "customer_name": f"{customer.first_name} {customer.last_name}" if customer else "N/A",
        "total_credit": f"{total_credit:.2f}",
        "total_debit": f"{total_debit:.2f}",
        "entry_count": len(entries),
        "entries": entries,
    }


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
    kind: Annotated[str | None, Query(pattern=r"^(OPENING_DEPOSIT|DEPOSIT|WITHDRAWAL|TRANSFER|ACCOUNT_STATUS|INTEREST|LOAN_DISBURSEMENT|LOAN_REPAYMENT|FD_OPEN|FD_MATURITY|FD_PREMATURE_CLOSURE)$")] = None,
):
    if start_at is not None and end_at is not None and start_at > end_at:
        raise HTTPException(status_code=422, detail="start_at must not be after end_at.")
    account, rows = _service(session, settings).get_statement(
        account_number, limit=limit, offset=offset, start_at=start_at, end_at=end_at, kind=kind,
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow((
        "account_number", "transaction_id", "date", "type", "credit", "debit",
        "running_balance", "status", "memo",
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
            getattr(row, "memo", "") or "",
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


# ─── Customer KYC & Profile ───────────────────────────────────────────────────

@app.patch("/customers/{customer_id}/kyc", tags=["customers"])
def update_kyc(
    customer_id: uuid.UUID,
    body: CustomerKycRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
):
    customer = session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    previous_status = customer.kyc_status
    customer.kyc_status = body.kyc_status
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="customer.kyc_updated",
            entity_type="customer",
            entity_id=str(customer.id),
            metadata_json={"previous": previous_status, "new": body.kyc_status},
        )
    )
    session.commit()
    return {
        "customer_id": str(customer.id),
        "kyc_status": customer.kyc_status,
    }


@app.patch("/customers/{customer_id}/profile", tags=["customers"])
def update_customer_profile(
    customer_id: uuid.UUID,
    body: CustomerUpdateRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
):
    customer = session.scalar(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if body.phone is not None:
        customer.phone = body.phone
    if body.email is not None:
        customer.email = body.email
    if body.address_line1 is not None:
        customer.address_line1 = body.address_line1
    if body.address_city is not None:
        customer.address_city = body.address_city
    if body.address_pin is not None:
        customer.address_pin = body.address_pin
    session.add(
        AuditEvent(
            actor_id=actor.id,
            action="customer.profile_updated",
            entity_type="customer",
            entity_id=str(customer.id),
        )
    )
    session.commit()
    return {
        "customer_id": str(customer.id),
        "phone": customer.phone,
        "email": customer.email,
        "address_line1": customer.address_line1,
        "address_city": customer.address_city,
        "address_pin": customer.address_pin,
    }


# ─── Cash Operations ──────────────────────────────────────────────────────────

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
        actor.id, idempotency_key, account_number, "DEPOSIT", body.amount, body.memo
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
        actor.id, idempotency_key, account_number, "WITHDRAWAL", body.amount, body.memo
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
        actor.id, idempotency_key,
        body.sender_account, body.receiver_account, body.amount, body.memo,
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


# ─── Interest Engine ──────────────────────────────────────────────────────────

@app.post("/accounts/{account_number}/interest", tags=["interest"])
def post_interest(
    account_number: str,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_month: Annotated[str, Query(pattern=r"^\d{4}-(?:0[1-9]|1[0-2])$")],
):
    """Post monthly savings interest to a savings/salary account."""
    result = _service(session, settings).post_monthly_interest(
        actor.id, idempotency_key, account_number, period_month
    )
    return _operation_response(result)


# ─── Loans ────────────────────────────────────────────────────────────────────

@app.post("/loans", status_code=201, tags=["loans"])
def apply_loan(
    body: LoanApplicationRequest,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Submit a new loan application."""
    loan = _service(session, settings).apply_loan(
        actor.id,
        body.account_number,
        body.loan_type,
        body.principal_amount,
        body.interest_rate_annual,
        body.tenure_months,
        body.memo,
    )
    session.commit()
    return {
        "loan_id": str(loan.id),
        "status": loan.status,
        "emi_minor": loan.emi_minor,
        "emi": f"{loan.emi_minor / 100:.2f}",
        "tenure_months": loan.tenure_months,
        "interest_rate_annual": str(loan.interest_rate_annual),
    }


@app.get("/loans", tags=["loans"])
def list_loans(
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Loan, Customer).join(Customer, Loan.customer_id == Customer.id)
    if status_filter:
        stmt = stmt.where(Loan.status == status_filter)
    rows = session.execute(
        stmt.order_by(Loan.created_at.desc()).limit(limit).offset(offset)
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id, action="loan.list", entity_type="loan", entity_id="collection"
        )
    )
    session.commit()
    return [
        {
            "loan_id": str(loan.id),
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "loan_type": loan.loan_type,
            "status": loan.status,
            "principal": f"{loan.principal_minor / 100:.2f}",
            "outstanding": f"{loan.outstanding_minor / 100:.2f}",
            "emi": f"{loan.emi_minor / 100:.2f}",
            "interest_rate_annual": str(loan.interest_rate_annual),
            "tenure_months": loan.tenure_months,
            "next_emi_date": str(loan.next_emi_date) if loan.next_emi_date else None,
            "created_at": loan.created_at.isoformat(),
        }
        for loan, customer in rows
    ]


@app.get("/loans/{loan_id}", tags=["loans"])
def get_loan(
    loan_id: uuid.UUID,
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
):
    loan = session.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found.")
    customer = session.get(Customer, loan.customer_id)
    repayments = session.scalars(
        select(LoanRepayment).where(LoanRepayment.loan_id == loan_id)
        .order_by(LoanRepayment.created_at.desc())
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id, action="loan.read", entity_type="loan", entity_id=str(loan.id)
        )
    )
    session.commit()
    return {
        "loan_id": str(loan.id),
        "customer_name": f"{customer.first_name} {customer.last_name}" if customer else "N/A",
        "loan_type": loan.loan_type,
        "status": loan.status,
        "principal": f"{loan.principal_minor / 100:.2f}",
        "outstanding": f"{loan.outstanding_minor / 100:.2f}",
        "emi": f"{loan.emi_minor / 100:.2f}",
        "interest_rate_annual": str(loan.interest_rate_annual),
        "tenure_months": loan.tenure_months,
        "next_emi_date": str(loan.next_emi_date) if loan.next_emi_date else None,
        "disbursed_at": loan.disbursed_at.isoformat() if loan.disbursed_at else None,
        "memo": loan.memo,
        "repayments": [
            {
                "id": str(r.id),
                "amount": f"{r.amount_minor / 100:.2f}",
                "principal": f"{r.principal_component_minor / 100:.2f}",
                "interest": f"{r.interest_component_minor / 100:.2f}",
                "date": r.created_at.isoformat(),
            }
            for r in repayments
        ],
    }


@app.post("/loans/{loan_id}/action", tags=["loans"])
def loan_action(
    loan_id: uuid.UUID,
    body: LoanActionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Approve, reject, or disburse a loan."""
    result = _service(session, settings).action_loan(
        actor.id, idempotency_key, loan_id, body.action, body.memo
    )
    session.commit()
    return result


@app.post("/loans/{loan_id}/repayments", tags=["loans"])
def repay_loan(
    loan_id: uuid.UUID,
    body: LoanRepaymentRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Post an EMI repayment against a loan."""
    result = _service(session, settings).repay_loan(
        actor.id, idempotency_key, loan_id, body.amount, body.memo
    )
    return _operation_response(result)


# ─── Fixed Deposits ───────────────────────────────────────────────────────────

@app.post("/fixed-deposits", status_code=201, tags=["fixed-deposits"])
def open_fd(
    body: FixedDepositOpenRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Open a new Fixed Deposit."""
    result = _service(session, settings).open_fd(
        actor.id, idempotency_key,
        body.account_number, body.principal_amount,
        body.interest_rate_annual, body.tenure_days,
    )
    session.commit()
    return result


@app.get("/fixed-deposits", tags=["fixed-deposits"])
def list_fds(
    actor: Annotated[object, Depends(require_roles("ADMIN", "TELLER", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(FixedDeposit, Customer).join(
        Customer, FixedDeposit.customer_id == Customer.id
    )
    if status_filter:
        stmt = stmt.where(FixedDeposit.status == status_filter)
    rows = session.execute(
        stmt.order_by(FixedDeposit.opened_at.desc()).limit(limit).offset(offset)
    ).all()
    session.add(
        AuditEvent(
            actor_id=actor.id, action="fd.list", entity_type="fixed_deposit", entity_id="collection"
        )
    )
    session.commit()
    return [
        {
            "fd_id": str(fd.id),
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "status": fd.status,
            "principal": f"{fd.principal_minor / 100:.2f}",
            "interest_rate_annual": str(fd.interest_rate_annual),
            "tenure_days": fd.tenure_days,
            "maturity_date": str(fd.maturity_date),
            "maturity_amount": f"{fd.maturity_amount_minor / 100:.2f}",
            "opened_at": fd.opened_at.isoformat(),
        }
        for fd, customer in rows
    ]


@app.post("/fixed-deposits/{fd_id}/close", tags=["fixed-deposits"])
def close_fd(
    fd_id: uuid.UUID,
    body: FixedDepositCloseRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    actor: Annotated[object, Depends(require_roles("ADMIN"))],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Close (mature or premature) a fixed deposit."""
    result = _service(session, settings).close_fd(
        actor.id, idempotency_key, fd_id, body.premature
    )
    session.commit()
    return result


# ─── Admin / Audit ────────────────────────────────────────────────────────────

@app.get("/admin/reconciliation", tags=["admin"])
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


@app.get("/admin/audit-logs", tags=["admin"])
def audit_logs(
    actor: Annotated[object, Depends(require_roles("ADMIN", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=100)] = None,
):
    query = (
        select(AuditEvent, StaffUser.username, StaffUser.full_name)
        .outerjoin(StaffUser, AuditEvent.actor_id == StaffUser.id)
    )
    if action and action.strip():
        query = query.where(AuditEvent.action.ilike(f"%{action.strip()}%"))
    query = (
        query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = session.execute(query).all()
    return [
        {
            "id": event.id,
            "actor_username": username or "System",
            "actor_name": full_name or "System",
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "metadata": event.metadata_json,
            "created_at": event.created_at.isoformat(),
        }
        for event, username, full_name in rows
    ]


@app.get("/admin/notifications", tags=["admin"])
def notification_logs(
    actor: Annotated[object, Depends(require_roles("ADMIN", "AUDITOR"))],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """View the simulated SMS/email notification log."""
    logs = session.scalars(
        select(NotificationLog)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        {
            "id": log.id,
            "channel": log.channel,
            "recipient": log.recipient,
            "subject": log.subject,
            "body": log.body,
            "status": log.status,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
