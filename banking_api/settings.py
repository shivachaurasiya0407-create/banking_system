import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    pii_hmac_key: str
    jwt_issuer: str
    access_token_minutes: int
    login_max_attempts: int
    login_lockout_minutes: int

    @classmethod
    def from_environment(cls):
        database_url = os.environ.get("DATABASE_URL", "").strip()
        jwt_secret = os.environ.get("JWT_SECRET", "")
        pii_hmac_key = os.environ.get("PII_HMAC_KEY", "")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required.")
        if not database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError(
                "DATABASE_URL must use the PostgreSQL psycopg driver."
            )
        if len(jwt_secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET must contain at least 32 bytes.")
        if len(pii_hmac_key.encode("utf-8")) < 32:
            raise RuntimeError("PII_HMAC_KEY must contain at least 32 bytes.")
        return cls(
            database_url=database_url,
            jwt_secret=jwt_secret,
            pii_hmac_key=pii_hmac_key,
            jwt_issuer=os.environ.get("JWT_ISSUER", "banking-system-local"),
            access_token_minutes=_positive_integer("ACCESS_TOKEN_MINUTES", 15),
            login_max_attempts=_positive_integer("LOGIN_MAX_ATTEMPTS", 5),
            login_lockout_minutes=_positive_integer("LOGIN_LOCKOUT_MINUTES", 15),
        )


def _positive_integer(name, default):
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a positive integer.") from error
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer.")
    return value
