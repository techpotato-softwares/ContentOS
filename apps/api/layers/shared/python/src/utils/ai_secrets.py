"""Platform + tenant BYOK AI secrets (Secrets Manager / local stub). Never log raw keys."""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

from config import get_app_config
from middleware.error_handler import AppError, ValidationError
from utils.logger import logger

_platform_cache: dict | None = None
_platform_expiry = 0
_TTL_MS = 5 * 60 * 1000


def _local_data_dir() -> Path:
    # apps/api/layers/shared/python/src/utils → apps/api
    root = Path(__file__).resolve().parents[5]
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


def _empty_keys() -> dict[str, str]:
    return {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}


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
            logger.warn(
                "Failed to read local BYOK blob",
                {"tenantId": tenant_id, "error": str(exc)},
            )
            raise AppError("BYOK keys could not be read", 400, "BYOK_KEYS_MISSING")

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_arn)
    data = json.loads(resp["SecretString"])
    return {
        "OPENAI_API_KEY": (data.get("OPENAI_API_KEY") or "").strip(),
        "GEMINI_API_KEY": (data.get("GEMINI_API_KEY") or "").strip(),
    }


def peek_tenant_ai_key_flags(tenant_id: int, secret_arn: str | None) -> dict[str, bool]:
    """Return configured booleans only — never raw key material."""
    if not secret_arn:
        return {"openaiConfigured": False, "geminiConfigured": False}
    try:
        keys = get_tenant_ai_secrets(tenant_id, secret_arn)
    except AppError:
        return {"openaiConfigured": False, "geminiConfigured": False}
    return {
        "openaiConfigured": bool((keys.get("OPENAI_API_KEY") or "").strip()),
        "geminiConfigured": bool((keys.get("GEMINI_API_KEY") or "").strip()),
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


def delete_tenant_ai_secrets(tenant_id: int, secret_arn: str | None) -> None:
    """Remove local stub or clear AWS secret values (do not log contents)."""
    if not secret_arn:
        return
    cfg = get_app_config()
    if secret_arn.startswith("local/") or cfg.is_local:
        path = _local_data_dir() / f"{tenant_id}.json"
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warn("Failed to delete local BYOK stub", {"tenantId": tenant_id, "error": str(exc)})
        return

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    try:
        client.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(_empty_keys()))
    except Exception as exc:
        logger.warn("Failed to clear tenant AI secret", {"tenantId": tenant_id, "error": str(exc)})


def merge_tenant_ai_secrets(
    tenant_id: int,
    secret_arn: str | None,
    *,
    openai_api_key: str | None = None,
    gemini_api_key: str | None = None,
    clear_openai: bool = False,
    clear_gemini: bool = False,
) -> str | None:
    """Merge key updates/clears. Returns new ARN or None when both keys cleared."""
    existing = _empty_keys()
    if secret_arn:
        try:
            existing = get_tenant_ai_secrets(tenant_id, secret_arn)
        except AppError:
            existing = _empty_keys()

    openai = (existing.get("OPENAI_API_KEY") or "").strip()
    gemini = (existing.get("GEMINI_API_KEY") or "").strip()

    if clear_openai:
        openai = ""
    elif openai_api_key is not None and str(openai_api_key).strip():
        openai = str(openai_api_key).strip()

    if clear_gemini:
        gemini = ""
    elif gemini_api_key is not None and str(gemini_api_key).strip():
        gemini = str(gemini_api_key).strip()

    if not openai and not gemini:
        delete_tenant_ai_secrets(tenant_id, secret_arn)
        return None

    return put_tenant_ai_secrets(
        tenant_id,
        {"OPENAI_API_KEY": openai, "GEMINI_API_KEY": gemini},
    )
