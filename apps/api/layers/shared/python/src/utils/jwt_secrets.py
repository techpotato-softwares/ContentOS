from __future__ import annotations
import os
import time
from dataclasses import dataclass
from utils.logger import logger
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

def get_jwt_secrets() -> JwtSecrets:
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache
    cfg = get_app_config()
    if cfg.is_local:
        _cache = _local()
        _expiry = now + _TTL
        return _cache
    secret_id = os.environ.get("JWT_SECRET_ID")
    if not secret_id:
        if cfg.environment == "prod":
            raise RuntimeError("JWT_SECRET_ID must be set in production")
        logger.warn("JWT_SECRET_ID not set, using environment variables")
        _cache = _local()
        _expiry = now + _TTL
        return _cache
    import json
    import boto3
    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    _cache = JwtSecrets(JWT_SECRET=data["JWT_SECRET"], JWT_REFRESH_SECRET=data["JWT_REFRESH_SECRET"])
    _expiry = now + _TTL
    return _cache

def clear_jwt_secrets_cache():
    global _cache, _expiry
    _cache = None
    _expiry = 0
