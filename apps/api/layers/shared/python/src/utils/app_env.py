from __future__ import annotations

import os


def is_production() -> bool:
    """True when APP_ENV=production (preferred) or ENVIRONMENT=prod/production."""
    app_env = (os.environ.get("APP_ENV") or "").strip().lower()
    if app_env in ("production", "prod"):
        return True
    environment = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    return environment in ("production", "prod")


def app_env_label() -> str:
    """Normalized APP_ENV for Lambda / docs (production | qa | dev | …)."""
    if is_production():
        return "production"
    app_env = (os.environ.get("APP_ENV") or "").strip()
    if app_env:
        return app_env.lower()
    return (os.environ.get("ENVIRONMENT") or "dev").strip().lower()
