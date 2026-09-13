"""Production auth hardening: seed creds, rate limits, JWT Secrets Manager."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers/shared/python/src"))

from middleware.error_handler import RateLimitError, create_error_response
from utils.app_env import is_production
from utils.jwt_secrets import clear_jwt_secrets_cache, get_jwt_secrets
from utils.rate_limit import (
    enforce_auth_rate_limit,
    reset_rate_limit_store_for_tests,
)
from utils.seed_credentials import (
    reject_seed_login_in_production,
    SEED_PASSWORD,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    clear_jwt_secrets_cache()
    reset_rate_limit_store_for_tests()
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_STORE", "memory")
    monkeypatch.setenv("AUTH_RATE_LIMIT_CAPACITY", "3")
    monkeypatch.setenv("AUTH_RATE_LIMIT_REFILL_PER_SEC", "0")
    yield
    clear_jwt_secrets_cache()
    reset_rate_limit_store_for_tests()


def test_is_production_respects_app_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert is_production() is True
    monkeypatch.setenv("APP_ENV", "dev")
    assert is_production() is False


def test_seed_login_allowed_outside_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    reject_seed_login_in_production("superadmin", SEED_PASSWORD)


def test_seed_login_blocked_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(Exception) as exc:
        reject_seed_login_in_production("superadmin", SEED_PASSWORD)
    err = exc.value
    assert getattr(err, "status_code", None) == 401
    assert getattr(err, "code", None) == "UNAUTHORIZED"


def test_seed_email_blocked_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(Exception) as exc:
        reject_seed_login_in_production("demo@demo-co.local", "any-password")
    assert getattr(exc.value, "status_code", None) == 401


def test_rate_limit_returns_429_on_burst():
    event = {"requestContext": {"identity": {"sourceIp": "203.0.113.9"}}}
    for _ in range(3):
        enforce_auth_rate_limit("login", identity="user@example.com", event=event)
    with pytest.raises(RateLimitError) as exc:
        enforce_auth_rate_limit("login", identity="user@example.com", event=event)
    resp = create_error_response(exc.value)
    assert resp["statusCode"] == 429
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "RATE_LIMITED"
    assert resp["headers"].get("Retry-After")


def test_jwt_secrets_require_secret_id_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET_ID", raising=False)
    monkeypatch.setenv("IS_LOCAL", "true")  # must still refuse local fallback
    clear_jwt_secrets_cache()
    with pytest.raises(RuntimeError, match="JWT_SECRET_ID"):
        get_jwt_secrets()


def test_jwt_secrets_load_from_secrets_manager_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_ID", "/contentos/prod/jwt")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    clear_jwt_secrets_cache()

    fake_client = MagicMock()
    fake_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "JWT_SECRET": "prod-access-secret",
                "JWT_REFRESH_SECRET": "prod-refresh-secret",
            }
        )
    }

    with patch("boto3.client", return_value=fake_client):
        secrets = get_jwt_secrets()

    assert secrets.JWT_SECRET == "prod-access-secret"
    assert secrets.JWT_REFRESH_SECRET == "prod-refresh-secret"
    fake_client.get_secret_value.assert_called_once_with(SecretId="/contentos/prod/jwt")


def test_jwt_secrets_local_dev_uses_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("JWT_SECRET", "dev-secret")
    monkeypatch.setenv("JWT_REFRESH_SECRET", "dev-refresh")
    clear_jwt_secrets_cache()
    secrets = get_jwt_secrets()
    assert secrets.JWT_SECRET == "dev-secret"
    assert secrets.JWT_REFRESH_SECRET == "dev-refresh"
