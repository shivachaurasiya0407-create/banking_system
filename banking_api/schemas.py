import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)
]
AccountNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")]
IdempotencyKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=128)
]


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

    @field_validator("country")
    @classmethod
    def validate_country(cls, value):
        if value.casefold() != "india":
            raise ValueError("This prototype currently supports India only.")
        return "India"

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
        from bank_system import INDIA_STATES

        canonical_states = {state.casefold(): state for state in INDIA_STATES}
        state = canonical_states.get(value.casefold())
        if state is None:
            raise ValueError("Enter a supported Indian state or union territory.")
        return state


class AccountOpenRequest(BaseModel):
    customer: CustomerCreate
    opening_deposit: Annotated[str, Field(min_length=1, max_length=24)]


class MoneyRequest(BaseModel):
    amount: Annotated[str, Field(min_length=1, max_length=24)]


class TransferRequest(BaseModel):
    sender_account: AccountNumber
    receiver_account: AccountNumber
    amount: Annotated[str, Field(min_length=1, max_length=24)]


class AccountStatusRequest(BaseModel):
    status: Annotated[str, Field(pattern=r"^(ACTIVE|FROZEN|CLOSED)$")]


class StaffCreateRequest(BaseModel):
    username: Username
    full_name: Annotated[str, Field(min_length=1, max_length=200)]
    role: Annotated[str, Field(pattern=r"^(ADMIN|TELLER|AUDITOR)$")]
    password: Annotated[str, Field(min_length=12, max_length=256)]

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if not (
            any(char.isupper() for char in value)
            and any(char.islower() for char in value)
            and any(char.isdigit() for char in value)
        ):
            raise ValueError(
                "Password must include uppercase, lowercase, and numeric characters."
            )
        return value


class StaffPasswordResetRequest(BaseModel):
    password: Annotated[str, Field(min_length=12, max_length=256)]

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if not (
            any(char.isupper() for char in value)
            and any(char.islower() for char in value)
            and any(char.isdigit() for char in value)
        ):
            raise ValueError(
                "Password must include uppercase, lowercase, and numeric characters."
            )
        return value
