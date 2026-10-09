from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from banking_api.settings import Settings


_session_factory = None


def configure_database(settings=None):
    global _session_factory
    settings = settings or Settings.from_environment()
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    return engine


def get_session() -> Generator[Session, None, None]:
    if _session_factory is None:
        configure_database()
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
