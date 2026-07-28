from __future__ import annotations
import json
import os
import time
from config import get_app_config, get_local_database_config, build_database_url, DatabaseConfig
from utils.logger import logger

_cache: DatabaseConfig | None = None
_expiry = 0
_TTL = 5 * 60 * 1000

def get_database_config() -> DatabaseConfig:
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache
    cfg = get_app_config()
    if cfg.is_local:
        _cache = get_local_database_config()
        _expiry = now + _TTL
        return _cache
    import boto3
    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=cfg.secrets_manager_secret_id)
    data = json.loads(resp["SecretString"])
    _cache = DatabaseConfig(
        host=cfg.database.host,
        port=cfg.database.port,
        database=cfg.database.database,
        username=data.get("username") or data.get("USERNAME"),
        password=data.get("password") or data.get("PASSWORD"),
        ssl=cfg.database.ssl,
    )
    _expiry = now + _TTL
    return _cache

def get_database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return build_database_url(get_database_config())

def clear_secrets_cache():
    global _cache, _expiry
    _cache = None
    _expiry = 0
