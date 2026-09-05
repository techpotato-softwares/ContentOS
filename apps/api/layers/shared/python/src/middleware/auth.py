from __future__ import annotations
from typing import Any
from middleware.error_handler import AppError, create_error_response
from utils.webtoken import verify_access_token, JWTPayload


def _normalize_user(user: JWTPayload) -> JWTPayload:
    normalized: dict[str, Any] = dict(user)
    if normalized.get("tenantId") is None and normalized.get("tenant_id") is not None:
        normalized["tenantId"] = normalized["tenant_id"]
    if normalized.get("role") is None and normalized.get("roleName") is not None:
        normalized["role"] = normalized["roleName"]
    return normalized  # type: ignore[return-value]


def _assert_token_version(user: JWTPayload) -> None:
    """Reject JWTs issued before a password reset (token_version mismatch)."""
    user_id = user.get("userId")
    if not user_id:
        raise AppError("Invalid token payload", 401, "UNAUTHORIZED")
    from database import get_session
    from database.models import User

    with get_session() as session:
        row = session.get(User, int(user_id))
        if not row or not row.is_active:
            raise AppError("Invalid or expired token", 401, "UNAUTHORIZED")
        expected = int(getattr(row, "token_version", 0) or 0)
        claimed = int(user.get("tv") or 0)
        if claimed != expected:
            raise AppError("Session expired — please sign in again", 401, "SESSION_REVOKED")
        # Keep emailVerified claim fresh for clients that trust JWT
        user["emailVerified"] = bool(row.email_verified_at)  # type: ignore[index]


def auth_middleware(event: dict) -> dict | dict:
    """Return event with user or an API Gateway error response."""
    try:
        headers = event.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth:
            return create_error_response(
                AppError("Authorization header is missing", 401, "UNAUTHORIZED")
            )
        if not auth.lower().startswith("bearer "):
            return create_error_response(
                AppError(
                    "Authorization header must start with Bearer",
                    401,
                    "UNAUTHORIZED",
                )
            )
        token = auth.split(" ", 1)[1].strip()
        if not token:
            return create_error_response(
                AppError("Token is missing", 401, "UNAUTHORIZED")
            )
        user = _normalize_user(verify_access_token(token))
        if not user.get("userId"):
            return create_error_response(
                AppError("Invalid token payload", 401, "UNAUTHORIZED")
            )
        _assert_token_version(user)
        return {**event, "user": user}
    except AppError as e:
        return create_error_response(e)
    except Exception as e:
        return create_error_response(
            AppError(str(e) or "Invalid or expired token", 401, "UNAUTHORIZED")
        )


def get_authenticated_user(event: dict) -> JWTPayload:
    user = event.get("user")
    if not user:
        raise AppError("Unauthenticated", 401, "UNAUTHORIZED")
    return _normalize_user(user)
