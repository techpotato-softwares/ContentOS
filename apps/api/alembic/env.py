from __future__ import annotations
import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "layers/shared/python/src"))

# Load apps/api/.env so alembic matches local uvicorn
_env_path = os.path.join(ROOT, ".env")
if os.path.exists(_env_path):
    for line in open(_env_path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

from database.models import SQLModel  # noqa: E402
from sqlmodel import SQLModel as _SM  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _resolve_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "5433")
    name = os.environ.get("DB_NAME", "contentos")
    user = os.environ.get("DB_USERNAME", "postgres")
    password = os.environ.get("DB_PASSWORD", "secret")
    ssl = os.environ.get("DB_SSL", "false").lower() == "true"
    q = "?sslmode=require" if ssl else ""
    return f"postgresql://{user}:{password}@{host}:{port}/{name}{q}"


def run_migrations_offline():
    url = _resolve_url() or config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
