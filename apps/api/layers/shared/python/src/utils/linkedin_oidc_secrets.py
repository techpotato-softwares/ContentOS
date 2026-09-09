"""LinkedIn OIDC login credentials — Secrets Manager in AWS, env locally.

Separate from LinkedIn *publishing* OAuth (LINKEDIN_CLIENT_* / /api/social/linkedin/*).

Secret id: /{APP}/{env}/linkedin-oidc
JSON keys: LINKEDIN_OIDC_CLIENT_ID, LINKEDIN_OIDC_CLIENT_SECRET
Redirect URIs stay in plain env (non-secret).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from config import get_app_config
from utils.logger import logger


@dataclass(frozen=True)
class LinkedInOidcSecrets:
    client_id: str
    client_secret: str


_cache: LinkedInOidcSecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000


def _from_env() -> LinkedInOidcSecrets:
    # Prefer OIDC-prefixed vars; fall back only for local convenience (never for redirect)
    client_id = (
        os.environ.get("LINKEDIN_OIDC_CLIENT_ID")
        or os.environ.get("LINKEDIN_LOGIN_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.environ.get("LINKEDIN_OIDC_CLIENT_SECRET")
        or os.environ.get("LINKEDIN_LOGIN_CLIENT_SECRET")
        or ""
    ).strip()
    return LinkedInOidcSecrets(client_id=client_id, client_secret=client_secret)


def get_linkedin_oidc_secrets() -> LinkedInOidcSecrets:
    """Load LinkedIn OIDC client id/secret. Never log secret values."""
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

    secret_id = (os.environ.get("LINKEDIN_OIDC_SECRET_ID") or "").strip()
    if not secret_id:
        if cfg.environment == "prod":
            raise RuntimeError("LINKEDIN_OIDC_SECRET_ID must be set in production")
        logger.warn("LINKEDIN_OIDC_SECRET_ID not set; falling back to env")
        secrets = _from_env()
        _cache = secrets
        _expiry = now + _TTL
        return secrets

    import json
    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    secrets = LinkedInOidcSecrets(
        client_id=str(
            data.get("LINKEDIN_OIDC_CLIENT_ID") or data.get("CLIENT_ID") or ""
        ).strip(),
        client_secret=str(
            data.get("LINKEDIN_OIDC_CLIENT_SECRET") or data.get("CLIENT_SECRET") or ""
        ).strip(),
    )
    _cache = secrets
    _expiry = now + _TTL
    return secrets


def clear_linkedin_oidc_secrets_cache() -> None:
    global _cache, _expiry
    _cache = None
    _expiry = 0


def linkedin_oidc_redirect_uri() -> str:
    """Login callback — must NOT be the publishing /api/social/linkedin/callback."""
    return (
        os.environ.get("LINKEDIN_OIDC_REDIRECT_URI")
        or "http://127.0.0.1:4001/api/auth/linkedin/callback"
    ).strip()


def linkedin_oidc_frontend_redirect() -> str:
    return (
        os.environ.get("LINKEDIN_OIDC_FRONTEND_REDIRECT")
        or os.environ.get("FRONTEND_URL")
        or "http://127.0.0.1:5173"
    ).rstrip("/")
