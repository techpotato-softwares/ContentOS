"""Google OAuth client credentials — Secrets Manager in AWS, env locally.

Secret id: /{APP}/{env}/google-oauth  (same pattern as /{APP}/{env}/jwt — ticket 0055 hygiene)
JSON keys: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
Redirect URIs stay in plain env (non-secret).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from config import get_app_config
from utils.logger import logger


@dataclass(frozen=True)
class GoogleOAuthSecrets:
    client_id: str
    client_secret: str


_cache: GoogleOAuthSecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000


def _from_env() -> GoogleOAuthSecrets:
    return GoogleOAuthSecrets(
        client_id=(os.environ.get("GOOGLE_CLIENT_ID") or "").strip(),
        client_secret=(os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip(),
    )


def get_google_oauth_secrets() -> GoogleOAuthSecrets:
    """Load Google OAuth client id/secret. Never log secret values."""
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache

    cfg = get_app_config()
    if cfg.is_local:
        secrets = _from_env()
        _cache = secrets
        _expiry = now + _TTL
        return secrets

    secret_id = (os.environ.get("GOOGLE_OAUTH_SECRET_ID") or "").strip()
    if not secret_id:
        if cfg.environment == "prod":
            raise RuntimeError("GOOGLE_OAUTH_SECRET_ID must be set in production")
        logger.warn("GOOGLE_OAUTH_SECRET_ID not set; falling back to env")
        secrets = _from_env()
        _cache = secrets
        _expiry = now + _TTL
        return secrets

    import json
    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    secrets = GoogleOAuthSecrets(
        client_id=str(data.get("GOOGLE_CLIENT_ID") or "").strip(),
        client_secret=str(data.get("GOOGLE_CLIENT_SECRET") or "").strip(),
    )
    _cache = secrets
    _expiry = now + _TTL
    return secrets


def clear_google_oauth_secrets_cache() -> None:
    global _cache, _expiry
    _cache = None
    _expiry = 0


def google_redirect_uri() -> str:
    return (
        os.environ.get("GOOGLE_REDIRECT_URI")
        or "http://127.0.0.1:4001/api/auth/google/callback"
    ).strip()


def google_frontend_redirect() -> str:
    return (
        os.environ.get("GOOGLE_FRONTEND_REDIRECT")
        or os.environ.get("FRONTEND_URL")
        or "http://127.0.0.1:5173"
    ).rstrip("/")
