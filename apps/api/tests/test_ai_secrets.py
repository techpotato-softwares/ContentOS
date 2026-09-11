"""Platform AI secrets + resolve_ai_credentials behavior."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers/shared/python/src"))
sys.path.insert(0, str(ROOT))

from middleware.error_handler import AppError, create_error_response  # noqa: E402
from utils.ai_secrets import (  # noqa: E402
    clear_ai_secrets_cache,
    get_platform_ai_secrets,
)
from modules.agent.src.providers import resolve_ai_credentials  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_ai_cache(monkeypatch):
    clear_ai_secrets_cache()
    # Default: local mode for isolated tests unless overridden
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "postgres")
    monkeypatch.delenv("AI_SECRET_ID", raising=False)
    yield
    clear_ai_secrets_cache()


def _non_local(monkeypatch):
    monkeypatch.setenv("IS_LOCAL", "false")
    monkeypatch.setenv("AWS_SAM_LOCAL", "false")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_NAME", "postgres")
    monkeypatch.setenv("ENVIRONMENT", "qa")


def test_local_env_resolution(monkeypatch):
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-local")
    monkeypatch.setenv("AI_PROVIDER", "gemini")

    secrets = get_platform_ai_secrets()
    assert secrets.OPENAI_API_KEY == "sk-local-openai"
    assert secrets.GEMINI_API_KEY == "gem-local"
    assert secrets.AI_PROVIDER == "gemini"

    creds = resolve_ai_credentials()
    assert creds.source == "env"
    assert creds.provider == "gemini"
    assert creds.gemini_api_key == "gem-local"


def test_local_never_calls_secrets_manager(monkeypatch):
    monkeypatch.setenv("IS_LOCAL", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-only-env")
    monkeypatch.setenv("AI_PROVIDER", "openai")

    with patch("boto3.client") as boto_client:
        secrets = get_platform_ai_secrets()
        assert secrets.OPENAI_API_KEY == "sk-only-env"
        boto_client.assert_not_called()


def test_non_local_uses_secrets_manager(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    payload = {
        "OPENAI_API_KEY": "sk-from-sm",
        "GEMINI_API_KEY": "gem-from-sm",
        "AI_PROVIDER": "openai",
    }
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": json.dumps(payload)}

    with patch("boto3.client", return_value=mock_client) as boto_client:
        secrets = get_platform_ai_secrets()
        boto_client.assert_called()
        mock_client.get_secret_value.assert_called_once_with(SecretId="/contentos/qa/ai")
        assert secrets.OPENAI_API_KEY == "sk-from-sm"
        assert secrets.GEMINI_API_KEY == "gem-from-sm"

        creds = resolve_ai_credentials()
        assert creds.source == "secrets_manager"
        assert creds.openai_api_key == "sk-from-sm"


def test_missing_ai_secret_id_non_local(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.delenv("AI_SECRET_ID", raising=False)

    with pytest.raises(RuntimeError, match="AI_SECRET_ID"):
        get_platform_ai_secrets()

    with pytest.raises(AppError) as excinfo:
        resolve_ai_credentials()
    assert excinfo.value.code == "AI_CONFIG"
    assert "AI_SECRET_ID" in excinfo.value.message


def test_missing_openai_key_non_local(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "gem", "AI_PROVIDER": "openai"}
        )
    }
    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(AppError) as excinfo:
            resolve_ai_credentials()
        assert excinfo.value.code == "AI_CONFIG"
        assert "OPENAI_API_KEY" in excinfo.value.message


def test_missing_gemini_key_non_local(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"OPENAI_API_KEY": "sk", "GEMINI_API_KEY": "", "AI_PROVIDER": "gemini"}
        )
    }
    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(AppError) as excinfo:
            resolve_ai_credentials()
        assert excinfo.value.code == "AI_CONFIG"
        assert "GEMINI_API_KEY" in excinfo.value.message


def test_malformed_secret_json(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {"SecretString": "{not-json"}
    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Unable to load"):
            get_platform_ai_secrets()

        clear_ai_secrets_cache()
        with pytest.raises(AppError) as excinfo:
            resolve_ai_credentials()
        assert excinfo.value.code == "AI_CONFIG"
        # Structured API response — no raw SM / parse stack details
        resp = create_error_response(excinfo.value)
        body = json.loads(resp["body"])
        assert body["error"]["code"] == "AI_CONFIG"
        assert "Traceback" not in body["error"]["message"]
        assert "SecretString" not in body["error"]["message"]


def test_secrets_manager_exception_not_leaked(monkeypatch):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")

    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = Exception(
        "AccessDeniedException: User arn:aws:iam::123 is not authorized"
    )
    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(AppError) as excinfo:
            resolve_ai_credentials()
        assert excinfo.value.code == "AI_CONFIG"
        assert "AccessDenied" not in excinfo.value.message
        assert "arn:aws" not in excinfo.value.message


def test_no_secret_values_in_logs(monkeypatch, capsys):
    _non_local(monkeypatch)
    monkeypatch.setenv("AI_SECRET_ID", "/contentos/qa/ai")
    secret_value = "sk-super-secret-should-not-log"

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "OPENAI_API_KEY": secret_value,
                "GEMINI_API_KEY": "gem-secret",
                "AI_PROVIDER": "openai",
            }
        )
    }
    with patch("boto3.client", return_value=mock_client):
        get_platform_ai_secrets()
        resolve_ai_credentials()

    out = capsys.readouterr().out
    assert secret_value not in out
    assert "gem-secret" not in out


def test_lambda_env_pattern_ai_secret_id_not_keys():
    """CDK must inject AI_SECRET_ID for agent/ai; never plaintext AI keys."""
    lambda_src = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "cdk_constructs"
        / "core"
        / "lambda_construct.py"
    ).read_text(encoding="utf-8")
    stack_src = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "stacks"
        / "api_stack.py"
    ).read_text(encoding="utf-8")

    assert "AiSecretsConstruct" in stack_src
    assert 'add_environment("AI_SECRET_ID"' in stack_src
    assert 'add_environment("OPENAI_API_KEY"' not in stack_src
    assert 'add_environment("GEMINI_API_KEY"' not in stack_src
    assert 'add_environment("OPENAI_API_KEY"' not in lambda_src
    assert 'add_environment("GEMINI_API_KEY"' not in lambda_src
    # Local env loader must scrub AI keys
    assert '"OPENAI_API_KEY"' in lambda_src  # blocked set
    assert "_blocked" in lambda_src
    # Models/flags OK; keys not in the shared environment dict as assignments
    env_block = lambda_src.split("environment: dict[str, str] = {", 1)[1].split(
        "}", 1
    )[0]
    assert "OPENAI_API_KEY" not in env_block
    assert "GEMINI_API_KEY" not in env_block
    assert "AI_SECRET_ID" not in env_block  # injected only on agent/ai in api_stack


def test_ai_secrets_construct_placeholder_keys_only():
    construct = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "cdk_constructs"
        / "security"
        / "ai_secrets_construct.py"
    ).read_text(encoding="utf-8")
    assert 'secret_name=config.ai_secret_id' in construct
    assert '"OPENAI_API_KEY": ""' in construct
    assert '"GEMINI_API_KEY": ""' in construct
    assert "sk-" not in construct
    assert "AIza" not in construct
