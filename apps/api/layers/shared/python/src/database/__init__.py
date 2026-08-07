from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

_engine = None
_SessionLocal = None


def _resolve_database_url() -> str:
    """Local: DB_* / DATABASE_URL from env. QA/Prod: credentials from Secrets Manager."""
    from utils.secrets import get_database_url

    return get_database_url()


def get_engine():
    global _engine
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, class_=Session
        )
    return _SessionLocal


def get_session() -> Session:
    return get_session_factory()()


def init_db():
    SQLModel.metadata.create_all(get_engine())
