import datetime
import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from banking_api.database import get_session
from banking_api.models import StaffUser
from banking_api.models import AuditEvent
from banking_api.security import verify_password
from banking_api.settings import Settings


bearer_scheme = HTTPBearer(auto_error=False)
DUMMY_PASSWORD_HASH = (
    "pbkdf2_sha256$600000$"
    + ("00" * 16)
    + "$"
    + ("00" * 32)
)


def get_settings():
    return Settings.from_environment()


def get_db() -> Generator[Session, None, None]:
    session_generator = get_session()
    session = next(session_generator)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session_generator.close()


def get_current_staff(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "iss", "sub"]},
        )
        staff_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    staff = session.scalar(select(StaffUser).where(StaffUser.id == staff_id))
    if staff is None or not staff.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff account is unavailable.",
        )
    session.commit()
    return staff


def require_roles(*roles):
    def role_dependency(staff=Depends(get_current_staff)):
        if staff.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return staff

    return role_dependency


def create_access_token(staff, settings):
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {
            "sub": str(staff.id),
            "role": staff.role,
            "iat": now,
            "exp": expires,
            "iss": settings.jwt_issuer,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def authenticate_staff(session, username, password, settings):
    normalized_username = username.strip().casefold()
    staff = session.scalar(
        select(StaffUser)
        .where(StaffUser.username == normalized_username)
        .with_for_update()
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    if staff is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None
    if not staff.active or (
        staff.locked_until is not None and staff.locked_until > now
    ):
        return None
    if not verify_password(password, staff.password_hash):
        staff.failed_login_attempts += 1
        if staff.failed_login_attempts >= settings.login_max_attempts:
            staff.locked_until = now + datetime.timedelta(
                minutes=settings.login_lockout_minutes
            )
            staff.failed_login_attempts = 0
        session.add(
            AuditEvent(
                actor_id=staff.id,
                action="auth.login_failed",
                entity_type="staff_user",
                entity_id=str(staff.id),
            )
        )
        session.commit()
        return None
    staff.failed_login_attempts = 0
    staff.locked_until = None
    session.add(
        AuditEvent(
            actor_id=staff.id,
            action="auth.login_succeeded",
            entity_type="staff_user",
            entity_id=str(staff.id),
        )
    )
    session.commit()
    return staff
