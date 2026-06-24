from __future__ import annotations

from contextlib import contextmanager
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


@contextmanager
def get_session():
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> str:
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    host = parsed.hostname or "postgres"
    db_name = (parsed.path or "/").lstrip("/") or "postgres"
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT current_database() AS db_name")).one()
        return f"{host} / {row.db_name or db_name}"
