"""Razorpay secrets. Never log secret values or expose them to the frontend."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from config import get_app_config
from middleware.error_handler import AppError, ValidationError
from utils.logger import logger


@dataclass(frozen=True)
class RazorpaySecrets:
    key_id: str
    key_secret: str
    webhook_secret: str
    plan_starter: str
    plan_growth: str
    plan_scale: str
    plan_agency: str


_cache: RazorpaySecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000


def _from_env() -> RazorpaySecrets:
    return RazorpaySecrets(
        key_id=(os.environ.get("RAZORPAY_KEY_ID") or "").strip(),
        key_secret=(os.environ.get("RAZORPAY_KEY_SECRET") or "").strip(),
        webhook_secret=(os.environ.get("RAZORPAY_WEBHOOK_SECRET") or "").strip(),
        plan_starter=(os.environ.get("RAZORPAY_PLAN_STARTER") or "").strip(),
        plan_growth=(os.environ.get("RAZORPAY_PLAN_GROWTH") or "").strip(),
        plan_scale=(os.environ.get("RAZORPAY_PLAN_SCALE") or "").strip(),
        plan_agency=(os.environ.get("RAZORPAY_PLAN_AGENCY") or "").strip(),
    )


def get_razorpay_secrets() -> RazorpaySecrets:
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache

    cfg = get_app_config()
    if cfg.is_local:
        _cache = _from_env()
        _expiry = now + _TTL
        return _cache

    secret_id = os.environ.get("RAZORPAY_SECRET_ID")
    if not secret_id:
        logger.warn("RAZORPAY_SECRET_ID not set; falling back to environment variables")
        _cache = _from_env()
        _expiry = now + _TTL
        return _cache

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    _cache = RazorpaySecrets(
        key_id=(data.get("RAZORPAY_KEY_ID") or "").strip(),
        key_secret=(data.get("RAZORPAY_KEY_SECRET") or "").strip(),
        webhook_secret=(data.get("RAZORPAY_WEBHOOK_SECRET") or "").strip(),
        plan_starter=(data.get("RAZORPAY_PLAN_STARTER") or "").strip(),
        plan_growth=(data.get("RAZORPAY_PLAN_GROWTH") or "").strip(),
        plan_scale=(data.get("RAZORPAY_PLAN_SCALE") or "").strip(),
        plan_agency=(data.get("RAZORPAY_PLAN_AGENCY") or "").strip(),
    )
    _expiry = now + _TTL
    return _cache


def clear_razorpay_secrets_cache() -> None:
    global _cache, _expiry
    _cache = None
    _expiry = 0


def require_razorpay_configured() -> RazorpaySecrets:
    secrets = get_razorpay_secrets()
    if not secrets.key_id or not secrets.key_secret:
        raise AppError("Razorpay is not configured", 503, "RAZORPAY_NOT_CONFIGURED")
    return secrets


def plan_tier_to_plan_id(tier: str, secrets: RazorpaySecrets | None = None) -> str:
    secrets = secrets or require_razorpay_configured()
    tier = (tier or "").strip().lower()
    mapping = {
        "starter": secrets.plan_starter,
        "growth": secrets.plan_growth,
        "scale": secrets.plan_scale,
        "agency": secrets.plan_agency,
    }
    plan_id = mapping.get(tier)
    if not plan_id:
        raise ValidationError(f"No Razorpay plan configured for tier: {tier}")
    return plan_id


def plan_id_to_plan_tier(plan_id: str | None, secrets: RazorpaySecrets | None = None) -> str | None:
    if not plan_id:
        return None
    secrets = secrets or get_razorpay_secrets()
    mapping = {
        secrets.plan_starter: "starter",
        secrets.plan_growth: "growth",
        secrets.plan_scale: "scale",
        secrets.plan_agency: "agency",
    }
    return mapping.get(plan_id)
