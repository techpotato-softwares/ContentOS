from __future__ import annotations
import os
import time
from dataclasses import dataclass
from utils.logger import logger
from utils.app_env import is_production
from config import get_app_config

@dataclass
class JwtSecrets:
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str

_cache: JwtSecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000

def _local() -> JwtSecrets:
    return JwtSecrets(
        JWT_SECRET=os.environ.get("JWT_SECRET", "local-dev-jwt-secret-change-me"),
        JWT_REFRESH_SECRET=os.environ.get("JWT_REFRESH_SECRET", "local-dev-refresh-secret-change-me"),
    )

def _from_secrets_manager(secret_id: str, region: str) -> JwtSecrets:
    import json
    import boto3

    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    secret = data.get("JWT_SECRET")
    refresh = data.get("JWT_REFRESH_SECRET")
    if not secret or not refresh:
        raise RuntimeError(
            f"Secret {secret_id} must contain JWT_SECRET and JWT_REFRESH_SECRET"
        )
    return JwtSecrets(JWT_SECRET=secret, JWT_REFRESH_SECRET=refresh)

def get_jwt_secrets() -> JwtSecrets:
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache
    cfg = get_app_config()
    secret_id = os.environ.get("JWT_SECRET_ID")

    # Production always loads from Secrets Manager (never local env fallbacks).
    if is_production():
        if not secret_id:
            raise RuntimeError("JWT_SECRET_ID must be set when APP_ENV=production")
        _cache = _from_secrets_manager(secret_id, cfg.region)
        _expiry = now + _TTL
        return _cache

    if cfg.is_local:
        _cache = _local()
        _expiry = now + _TTL
        return _cache

    if not secret_id:
        if cfg.environment in ("prod", "production"):
            raise RuntimeError("JWT_SECRET_ID must be set in production")
        logger.warn("JWT_SECRET_ID not set, using environment variables")
        _cache = _local()
        _expiry = now + _TTL
        return _cache

    _cache = _from_secrets_manager(secret_id, cfg.region)
    _expiry = now + _TTL
    return _cache

def clear_jwt_secrets_cache():
    global _cache, _expiry
    _cache = None
    _expiry = 0
