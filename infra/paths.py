"""Shared path helpers for ContentOS Python CDK."""
from __future__ import annotations

from pathlib import Path

# ContentOS/infra/
CDK_ROOT = Path(__file__).resolve().parent
# ContentOS/
REPO_ROOT = CDK_ROOT.parent
# ContentOS/apps/api/
API_ROOT = REPO_ROOT / "apps" / "api"
LAYER_BUNDLED = API_ROOT / "layers" / "shared" / "python" / "bundled"
MANIFEST_PATH = API_ROOT / "app-manifest.json"
ENV_LOCAL_JSON = CDK_ROOT / "env.local.json"
UI_BUILD_PATH = REPO_ROOT / "apps" / "web" / "dist"
MARKETING_PATH = REPO_ROOT / "apps" / "marketing"

API_ASSET_EXCLUDES = [
    ".venv",
    ".venv/**",
    "layers",
    "layers/**",
    "tests",
    "tests/**",
    "scripts",
    "scripts/**",
    "alembic",
    "alembic/**",
    "**/__pycache__",
    "**/*.pyc",
    "**/.pytest_cache",
    "*.md",
    ".git",
    ".git/**",
    ".env*",
    "*.log",
    "openapi",
    "openapi/**",
]
