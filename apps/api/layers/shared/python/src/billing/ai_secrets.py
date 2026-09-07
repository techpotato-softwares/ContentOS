"""Platform + tenant BYOK AI secrets (Secrets Manager / local stub). Never log raw keys."""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from config import get_app_config
from middleware.error_handler import AppError, ValidationError

_platform_cache: dict | None = None
_platform_expiry = 0
_TTL_MS = 5 * 60 * 1000


def _local_data_dir() -> Path:
    root = Path(__file__).resolve().parents[4]  # apps/api
    dest = root / ".data" / "tenant_ai"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _obfuscate(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _deobfuscate(blob: str) -> dict:
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def clear_platform_ai_secrets_cache() -> None:
    global _platform_cache, _platform_expiry
    _platform_cache = None
    _platform_expiry = 0


def get_platform_ai_secrets() -> dict:
    """Load platform OpenAI/Gemini keys from env (local) or AI_SECRET_ID (AWS)."""
    global _platform_cache, _platform_expiry
    now = int(time.time() * 1000)
    if _platform_cache and _platform_expiry > now:
        return dict(_platform_cache)

    cfg = get_app_config()
    provider = (os.environ.get("AI_PROVIDER") or "").lower().strip()

    if cfg.is_local or provider == "stub":
        data = {
            "OPENAI_API_KEY": (os.environ.get("OPENAI_API_KEY") or "").strip(),
            "GEMINI_API_KEY": (os.environ.get("GEMINI_API_KEY") or "").strip(),
            "AI_PROVIDER": provider or (os.environ.get("AI_PROVIDER") or "openai"),
        }
        _platform_cache = data
        _platform_expiry = now + _TTL_MS
        return dict(data)

    secret_id = (os.environ.get("AI_SECRET_ID") or "").strip()
    if not secret_id:
        # Dev/QA without SM: fall back to process env once
        if cfg.environment in ("prod", "production"):
            raise AppError(
                "Platform AI secret is not configured (AI_SECRET_ID).",
                500,
                "AI_CONFIG",
            )
        logger.warn("AI_SECRET_ID not set; using process environment for platform AI keys")
        data = {
            "OPENAI_API_KEY": (os.environ.get("OPENAI_API_KEY") or "").strip(),
            "GEMINI_API_KEY": (os.environ.get("GEMINI_API_KEY") or "").strip(),
            "AI_PROVIDER": provider or "openai",
        }
        _platform_cache = data
        _platform_expiry = now + _TTL_MS
        return dict(data)

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    normalized = {
        "OPENAI_API_KEY": (data.get("OPENAI_API_KEY") or "").strip(),
        "GEMINI_API_KEY": (data.get("GEMINI_API_KEY") or "").strip(),
        "AI_PROVIDER": (data.get("AI_PROVIDER") or provider or "openai"),
    }
    _platform_cache = normalized
    _platform_expiry = now + _TTL_MS
    return dict(normalized)


def get_tenant_ai_secrets(tenant_id: int, secret_arn: str | None) -> dict:
    """Decrypt/load tenant BYOK keys. Local stub uses .data/tenant_ai/{id}.json."""
    if not secret_arn:
        raise AppError(
            "BYOK keys are not configured for this tenant",
            400,
            "BYOK_KEYS_MISSING",
        )

    cfg = get_app_config()
    if secret_arn.startswith("local/") or cfg.is_local:
        path = _local_data_dir() / f"{tenant_id}.json"
        if not path.exists():
            raise AppError(
                "BYOK keys are missing. Save OpenAI/Gemini keys in AI settings.",
                400,
                "BYOK_KEYS_MISSING",
            )
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if "blob" in stored:
                return _deobfuscate(stored["blob"])
            return {
                "OPENAI_API_KEY": (stored.get("OPENAI_API_KEY") or "").strip(),
                "GEMINI_API_KEY": (stored.get("GEMINI_API_KEY") or "").strip(),
            }
        except AppError:
            raise
        except Exception as exc:
            logger.warn("Failed to read local BYOK blob", {"tenantId": tenant_id, "error": str(exc)})
            raise AppError("BYOK keys could not be read", 400, "BYOK_KEYS_MISSING")

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_arn)
    data = json.loads(resp["SecretString"])
    return {
        "OPENAI_API_KEY": (data.get("OPENAI_API_KEY") or "").strip(),
        "GEMINI_API_KEY": (data.get("GEMINI_API_KEY") or "").strip(),
    }


def put_tenant_ai_secrets(tenant_id: int, keys: dict) -> str:
    """Create/update tenant BYOK secret; returns secret name/ARN to store on tenant."""
    cfg = get_app_config()
    payload = {
        "OPENAI_API_KEY": (keys.get("OPENAI_API_KEY") or keys.get("openaiApiKey") or "").strip(),
        "GEMINI_API_KEY": (keys.get("GEMINI_API_KEY") or keys.get("geminiApiKey") or "").strip(),
    }
    if not payload["OPENAI_API_KEY"] and not payload["GEMINI_API_KEY"]:
        raise ValidationError("At least one of openaiApiKey or geminiApiKey is required")

    if cfg.is_local:
        path = _local_data_dir() / f"{tenant_id}.json"
        path.write_text(
            json.dumps({"blob": _obfuscate(payload)}, indent=0),
            encoding="utf-8",
        )
        return f"local/{cfg.app_name}/tenants/{tenant_id}/ai"

    import boto3

    name = f"/{cfg.app_name}/{cfg.environment}/tenants/{tenant_id}/ai"
    client = boto3.client("secretsmanager", region_name=cfg.region)
    body = json.dumps(payload)
    try:
        client.put_secret_value(SecretId=name, SecretString=body)
    except client.exceptions.ResourceNotFoundException:
        client.create_secret(Name=name, SecretString=body)
    return name
