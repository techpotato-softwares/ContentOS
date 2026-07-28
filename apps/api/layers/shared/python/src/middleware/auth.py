from __future__ import annotations
from typing import Any
from middleware.error_handler import AppError, create_error_response
from utils.webtoken import verify_access_token, JWTPayload

def auth_middleware(event: dict) -> dict | dict:
    """Return event with user or an API Gateway error response."""
    try:
        headers = event.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth:
            return create_error_response(AppError("Authorization header is missing", 401, "UNAUTHORIZED"))
        if not auth.lower().startswith("bearer "):
            return create_error_response(AppError("Authorization header must start with Bearer", 401, "UNAUTHORIZED"))
        token = auth.split(" ", 1)[1].strip()
        if not token:
            return create_error_response(AppError("Token is missing", 401, "UNAUTHORIZED"))
        user = verify_access_token(token)
        return {**event, "user": user}
    except Exception as e:
        return create_error_response(AppError(str(e) or "Invalid or expired token", 401, "UNAUTHORIZED"))

def get_authenticated_user(event: dict) -> JWTPayload:
    user = event.get("user")
    if not user:
        raise AppError("Unauthenticated", 401, "UNAUTHORIZED")
    return user
