from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

_engine = None
_SessionLocal = None


def _resolve_database_url() -> str:
    """Prefer DB_* components (password URL-encoded). Raw DATABASE_URL only if no DB_HOST."""
    from config import get_local_database_config, build_database_url

    if os.environ.get("DB_HOST"):
        return build_database_url(get_local_database_config())

    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    return build_database_url(get_local_database_config())


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
