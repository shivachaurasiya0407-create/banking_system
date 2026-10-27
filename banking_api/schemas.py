import re
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from banking_api.locations import INDIA_STATES

Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)
]
AccountNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]
IdempotencyKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
]


def _uppercase_text(value):
    return value.upper() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    username: Username
    password: Annotated[str, Field(min_length=1, max_length=256)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class CustomerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: Annotated[str, Field(min_length=1, max_length=100)]
    last_name: Annotated[str, Field(min_length=1, max_length=100)]
    phone: Annotated[str, Field(min_length=8, max_length=16)]
    age: Annotated[int, Field(ge=18, le=110)]
    country: Annotated[str, Field(min_length=1, max_length=100)]
    state: Annotated[str, Field(min_length=1, max_length=100)]
    identity_number: Annotated[str, Field(pattern=r"^[0-9]{12}$")]
    # Optional extended KYC fields
    email: Annotated[str | None, Field(default=None, max_length=200)] = None
    address_line1: Annotated[str | None, Field(default=None, max_length=250)] = None
    address_city: Annotated[str | None, Field(default=None, max_length=100)] = None
    address_pin: Annotated[str | None, Field(default=None, max_length=10)] = None

    @field_validator("country")
    @classmethod
    def validate_country(cls, value):
        if value.casefold() != "india":
            raise ValueError("This system currently supports India only.")
        return "INDIA"

    @field_validator("first_name", "last_name", "address_line1", "address_city", mode="before")
    @classmethod
    def uppercase_profile_text(cls, value):
        return _uppercase_text(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value):
        if not all(char.isalpha() or char in " -'" for char in value):
            raise ValueError("Name contains unsupported characters.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if not re.fullmatch(r"\+?[0-9]{8,15}", value):
            raise ValueError("Phone must contain 8 to 15 digits, optionally prefixed by +.")
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value):
        canonical_states = {state.casefold(): state for state in INDIA_STATES}
        state = canonical_states.get(value.casefold())
        if state is None:
            raise ValueError("Enter a supported Indian state or union territory.")
        return state.upper()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value.lower()


class CustomerUpdateRequest(BaseModel):
    """Update mutable customer profile fields."""

    model_config = ConfigDict(str_strip_whitespace=True)

    phone: Annotated[str | None, Field(default=None, min_length=8, max_length=16)] = None
    email: Annotated[str | None, Field(default=None, max_length=200)] = None
    address_line1: Annotated[str | None, Field(default=None, max_length=250)] = None
    address_city: Annotated[str | None, Field(default=None, max_length=100)] = None
    address_pin: Annotated[str | None, Field(default=None, max_length=10)] = None

    @field_validator("address_line1", "address_city", mode="before")
    @classmethod
    def uppercase_address_text(cls, value):
        return _uppercase_text(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"\+?[0-9]{8,15}", value):
            raise ValueError("Phone must contain 8 to 15 digits, optionally prefixed by +.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value.lower()

    @model_validator(mode="after")
    def require_at_least_one(self):
        if all(
            v is None
            for v in (self.phone, self.email, self.address_line1, self.address_city, self.address_pin)
        ):
            raise ValueError("Provide at least one field to update.")
        return self


class CustomerKycRequest(BaseModel):
    kyc_status: Annotated[str, Field(pattern=r"^(PENDING|VERIFIED|REJECTED)$")]


class AccountOpenRequest(BaseModel):
    customer: CustomerCreate
    opening_deposit: Annotated[str, Field(min_length=1, max_length=24)]
    branch_ifsc: Annotated[str, Field(min_length=4, max_length=20, pattern=r"^[A-Z0-9]+$")] = "SHIV0000001"
    account_type: Annotated[str, Field(pattern=r"^(SAVINGS|CURRENT|SALARY)$")] = "SAVINGS"


class BranchCreateRequest(BaseModel):
    ifsc: Annotated[str, Field(min_length=4, max_length=20, pattern=r"^[A-Z0-9]+$")]
    name: Annotated[str, Field(min_length=2, max_length=150)]

    @field_validator("name", mode="before")
    @classmethod
    def uppercase_name(cls, value):
        return _uppercase_text(value)


class MoneyRequest(BaseModel):
    amount: Annotated[str, Field(min_length=1, max_length=24)]
    memo: Annotated[str, Field(default="", max_length=250)] = ""

    @field_validator("memo", mode="before")
    @classmethod
    def uppercase_memo(cls, value):
        return _uppercase_text(value)


class TransferRequest(BaseModel):
    sender_account: AccountNumber
    receiver_account: AccountNumber
    amount: Annotated[str, Field(min_length=1, max_length=24)]
    memo: Annotated[str, Field(default="", max_length=250)] = ""

    @field_validator("memo", mode="before")
    @classmethod
    def uppercase_memo(cls, value):
        return _uppercase_text(value)


class AccountStatusRequest(BaseModel):
    status: Annotated[str, Field(pattern=r"^(ACTIVE|FROZEN|CLOSED)$")]


class TransactionReversalRequest(BaseModel):
    reason: Annotated[str, Field(min_length=5, max_length=250)]

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Reversal reason must contain at least five characters.")
        return value.upper()


class StaffCreateRequest(BaseModel):
    username: Username
    full_name: Annotated[str, Field(min_length=1, max_length=200)]
    role: Annotated[str, Field(pattern=r"^(ADMIN|TELLER|AUDITOR)$")]
    password: Annotated[str, Field(min_length=12, max_length=256)]

    @field_validator("full_name", mode="before")
    @classmethod
    def uppercase_full_name(cls, value):
        return _uppercase_text(value)


class StaffChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Annotated[str, Field(min_length=12, max_length=256)]


class StaffPasswordResetRequest(BaseModel):
    password: Annotated[str, Field(min_length=12, max_length=256)]


class StaffUpdateRequest(BaseModel):
    role: Annotated[str | None, Field(pattern=r"^(ADMIN|TELLER|AUDITOR)$")] = None
    active: bool | None = None

    @model_validator(mode="after")
    def require_an_update(self):
        if self.role is None and self.active is None:
            raise ValueError("Provide a new role or active status.")
        return self


# ─── Loan schemas ─────────────────────────────────────────────────────────────

class LoanApplicationRequest(BaseModel):
    """Apply for a new loan."""

    account_number: AccountNumber  # linked savings/current account
    loan_type: Annotated[str, Field(pattern=r"^(PERSONAL|HOME|VEHICLE|EDUCATION|GOLD)$")]
    principal_amount: Annotated[str, Field(min_length=1, max_length=24)]
    interest_rate_annual: Annotated[Decimal, Field(gt=0, le=36)]
    tenure_months: Annotated[int, Field(ge=1, le=360)]
    memo: Annotated[str, Field(default="", max_length=500)] = ""

    @field_validator("memo", mode="before")
    @classmethod
    def uppercase_memo(cls, value):
        return _uppercase_text(value)


class LoanActionRequest(BaseModel):
    """Approve / reject / disburse a loan."""

    action: Annotated[str, Field(pattern=r"^(APPROVE|REJECT|DISBURSE)$")]
    memo: Annotated[str, Field(default="", max_length=500)] = ""

    @field_validator("memo", mode="before")
    @classmethod
    def uppercase_memo(cls, value):
        return _uppercase_text(value)


class LoanRepaymentRequest(BaseModel):
    """Post an EMI or part-payment against a loan."""

    amount: Annotated[str, Field(min_length=1, max_length=24)]
    memo: Annotated[str, Field(default="", max_length=250)] = ""

    @field_validator("memo", mode="before")
    @classmethod
    def uppercase_memo(cls, value):
        return _uppercase_text(value)


# ─── Fixed Deposit schemas ────────────────────────────────────────────────────

class FixedDepositOpenRequest(BaseModel):
    """Open a new FD by debiting from a savings/current account."""

    account_number: AccountNumber  # source account
    principal_amount: Annotated[str, Field(min_length=1, max_length=24)]
    interest_rate_annual: Annotated[Decimal, Field(gt=0, le=15)]
    tenure_days: Annotated[int, Field(ge=7, le=3650)]


class FixedDepositCloseRequest(BaseModel):
    """Close an FD (mature or premature)."""

    premature: bool = False
