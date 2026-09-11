"""Platform AI credentials: local .env or AWS Secrets Manager (never log values)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from config import get_app_config
from utils.logger import logger

_cache: PlatformAiSecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000


@dataclass(frozen=True)
class PlatformAiSecrets:
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    AI_PROVIDER: str


def _strip(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().strip('"').strip("'")


def _from_env() -> PlatformAiSecrets:
    return PlatformAiSecrets(
        OPENAI_API_KEY=_strip(os.environ.get("OPENAI_API_KEY")),
        GEMINI_API_KEY=_strip(os.environ.get("GEMINI_API_KEY")),
        AI_PROVIDER=_strip(os.environ.get("AI_PROVIDER") or "openai") or "openai",
    )


def _parse_secret_payload(raw: str) -> PlatformAiSecrets:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("AI secret payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("AI secret payload must be a JSON object")
    return PlatformAiSecrets(
        OPENAI_API_KEY=_strip(data.get("OPENAI_API_KEY")),
        GEMINI_API_KEY=_strip(data.get("GEMINI_API_KEY")),
        AI_PROVIDER=_strip(data.get("AI_PROVIDER") or "openai") or "openai",
    )


def get_platform_ai_secrets() -> PlatformAiSecrets:
    """Return platform AI keys.

    Local (`IS_LOCAL=true`): read `apps/api/.env` / process env only ΓÇö never call SM.
    QA/Prod: read JSON from Secrets Manager using `AI_SECRET_ID`.
    """
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache

    cfg = get_app_config()
    if cfg.is_local:
        _cache = _from_env()
        _expiry = now + _TTL
        return _cache

    secret_id = (os.environ.get("AI_SECRET_ID") or "").strip()
    if not secret_id:
        logger.warn("AI_SECRET_ID is not set in non-local environment")
        raise RuntimeError("AI_SECRET_ID must be set outside local development")

    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=cfg.region)
        resp = client.get_secret_value(SecretId=secret_id)
        secret_string = resp.get("SecretString") or ""
        parsed = _parse_secret_payload(secret_string)
    except RuntimeError:
        raise
    except Exception:
        # Never surface SM exception text (may include ARNs / request ids)
        logger.warn(
            "Failed to load platform AI secret from Secrets Manager",
            {"secret_id_set": True},
        )
        raise RuntimeError("Unable to load platform AI credentials") from None

    logger.info(
        "Loaded platform AI secrets from Secrets Manager",
        {
            "openai_key_present": bool(parsed.OPENAI_API_KEY),
            "gemini_key_present": bool(parsed.GEMINI_API_KEY),
            "provider": parsed.AI_PROVIDER,
        },
    )
    _cache = parsed
    _expiry = now + _TTL
    return _cache


def clear_ai_secrets_cache() -> None:
    global _cache, _expiry
    _cache = None
    _expiry = 0
