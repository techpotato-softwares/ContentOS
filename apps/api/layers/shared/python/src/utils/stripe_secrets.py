"""Stripe secrets + client helpers. Never log secret values or full webhook payloads."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from config import get_app_config
from middleware.error_handler import AppError, ValidationError
from utils.logger import logger


@dataclass(frozen=True)
class StripeSecrets:
    secret_key: str
    webhook_secret: str
    price_starter: str
    price_growth: str
    price_scale: str
    price_agency: str


_cache: StripeSecrets | None = None
_expiry = 0
_TTL = 5 * 60 * 1000


def _from_env() -> StripeSecrets:
    return StripeSecrets(
        secret_key=(os.environ.get("STRIPE_SECRET_KEY") or "").strip(),
        webhook_secret=(os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip(),
        price_starter=(os.environ.get("STRIPE_PRICE_STARTER") or "").strip(),
        price_growth=(os.environ.get("STRIPE_PRICE_GROWTH") or "").strip(),
        price_scale=(os.environ.get("STRIPE_PRICE_SCALE") or "").strip(),
        price_agency=(os.environ.get("STRIPE_PRICE_AGENCY") or "").strip(),
    )


def get_stripe_secrets() -> StripeSecrets:
    global _cache, _expiry
    now = int(time.time() * 1000)
    if _cache and _expiry > now:
        return _cache

    cfg = get_app_config()
    if cfg.is_local:
        _cache = _from_env()
        _expiry = now + _TTL
        return _cache

    secret_id = os.environ.get("STRIPE_SECRET_ID")
    if not secret_id:
        logger.warn("STRIPE_SECRET_ID not set; falling back to environment variables")
        _cache = _from_env()
        _expiry = now + _TTL
        return _cache

    import boto3

    client = boto3.client("secretsmanager", region_name=cfg.region)
    resp = client.get_secret_value(SecretId=secret_id)
    data = json.loads(resp["SecretString"])
    _cache = StripeSecrets(
        secret_key=(data.get("STRIPE_SECRET_KEY") or "").strip(),
        webhook_secret=(data.get("STRIPE_WEBHOOK_SECRET") or "").strip(),
        price_starter=(data.get("STRIPE_PRICE_STARTER") or "").strip(),
        price_growth=(data.get("STRIPE_PRICE_GROWTH") or "").strip(),
        price_scale=(data.get("STRIPE_PRICE_SCALE") or "").strip(),
        price_agency=(data.get("STRIPE_PRICE_AGENCY") or "").strip(),
    )
    _expiry = now + _TTL
    return _cache


def clear_stripe_secrets_cache() -> None:
    global _cache, _expiry
    _cache = None
    _expiry = 0


def require_stripe_configured() -> StripeSecrets:
    secrets = get_stripe_secrets()
    if not secrets.secret_key:
        raise AppError("Stripe is not configured", 503, "STRIPE_NOT_CONFIGURED")
    return secrets


def price_id_to_plan_tier(price_id: str | None, secrets: StripeSecrets | None = None) -> str | None:
    if not price_id:
        return None
    secrets = secrets or get_stripe_secrets()
    mapping = {
        secrets.price_starter: "starter",
        secrets.price_growth: "growth",
        secrets.price_scale: "scale",
        secrets.price_agency: "agency",
    }
    return mapping.get(price_id)


def plan_tier_to_price_id(tier: str, secrets: StripeSecrets | None = None) -> str:
    secrets = secrets or require_stripe_configured()
    tier = (tier or "").strip().lower()
    mapping = {
        "starter": secrets.price_starter,
        "growth": secrets.price_growth,
        "scale": secrets.price_scale,
        "agency": secrets.price_agency,
    }
    price = mapping.get(tier)
    if not price:
        raise ValidationError(f"No Stripe price configured for plan: {tier}")
    return price


def get_stripe():
    """Return configured stripe module (lazy import)."""
    secrets = require_stripe_configured()
    import stripe

    stripe.api_key = secrets.secret_key
    return stripe
