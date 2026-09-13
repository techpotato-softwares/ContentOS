"""Known local/dev seed credentials — must never authenticate in production."""
from __future__ import annotations

from middleware.error_handler import AppError
from utils.app_env import is_production

# Matches apps/api/scripts/seed.py
SEED_USERNAMES = frozenset({"superadmin", "demo"})
SEED_EMAILS = frozenset({"superadmin@contentos.local", "demo@demo-co.local"})
SEED_PASSWORD = "ChangeMe123!"


def normalize_identity(value: str | None) -> str:
    return (value or "").strip().lower()


def is_seed_identity(username_or_email: str | None) -> bool:
    ident = normalize_identity(username_or_email)
    if not ident:
        return False
    return ident in {u.lower() for u in SEED_USERNAMES} or ident in {
        e.lower() for e in SEED_EMAILS
    }


def is_seed_password(password: str | None) -> bool:
    return (password or "") == SEED_PASSWORD


def is_known_seed_credential(username_or_email: str | None, password: str | None) -> bool:
    return is_seed_identity(username_or_email) and is_seed_password(password)


def reject_seed_login_in_production(username_or_email: str | None, password: str | None) -> None:
    """Block seed identities / known seed password combos when APP_ENV=production."""
    if not is_production():
        return
    if is_seed_identity(username_or_email) or is_known_seed_credential(
        username_or_email, password
    ):
        raise AppError("Invalid username or password", 401, "UNAUTHORIZED")
