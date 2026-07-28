from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class DatabaseConnectionConfig:
    host: str
    port: int
    database: str
    ssl: bool

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl: bool

@dataclass
class AppConfig:
    environment: str
    is_local: bool
    secrets_manager_secret_id: str
    region: str
    app_name: str
    database: DatabaseConnectionConfig

def _require_env(name: str, fallback: str | None = None) -> str:
    value = os.environ.get(name, fallback)
    if value is None or value == "":
        raise RuntimeError(
            f"{name} must be set. Copy python/.env.example and provide secrets via env or Secrets Manager."
        )
    return value

def get_app_config() -> AppConfig:
    environment = os.environ.get("ENVIRONMENT", "dev")
    is_local = os.environ.get("AWS_SAM_LOCAL") == "true" or os.environ.get("IS_LOCAL") == "true"
    app_name = os.environ.get("APP_NAME", "contentos")
    return AppConfig(
        environment=environment,
        is_local=is_local,
        app_name=app_name,
        secrets_manager_secret_id=os.environ.get("DB_SECRET_ID", f"/{app_name}/{environment}/db"),
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "ap-south-1",
        database=DatabaseConnectionConfig(
            host=os.environ.get("DB_HOST", "localhost") if is_local else _require_env("DB_HOST"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "postgres") if is_local else _require_env("DB_NAME"),
            ssl=os.environ.get("DB_SSL", "true").lower() == "true",
        ),
    )

def get_local_database_config() -> DatabaseConfig:
    is_local = os.environ.get("IS_LOCAL") == "true"
    # Prefer DATABASE_URL pieces; default SSL on for Supabase
    ssl_default = "true"
    return DatabaseConfig(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "postgres"),
        username=_require_env("DB_USERNAME", "postgres" if is_local else None),
        password=_require_env("DB_PASSWORD", "secret" if is_local else None),
        ssl=os.environ.get("DB_SSL", ssl_default).lower() == "true",
    )

def build_database_url(config: DatabaseConfig) -> str:
    from urllib.parse import quote_plus
    pwd = quote_plus(config.password)
    ssl = "?sslmode=require" if config.ssl else ""
    return f"postgresql://{config.username}:{pwd}@{config.host}:{config.port}/{config.database}{ssl}"
