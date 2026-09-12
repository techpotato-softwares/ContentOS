from __future__ import annotations
import os
import time
from typing import Any, TypedDict
import jwt
from utils.jwt_secrets import get_jwt_secrets

class JWTPayload(TypedDict, total=False):
    userId: int
    username: str
    email: str
    role: str
    tenantId: int
    permissions: list[str]
    modulesEnabled: list[str]
    emailVerified: bool
    tv: int  # token_version — bump on password reset to invalidate sessions

def _expiry(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default)

def _to_seconds(expiry: str) -> int:
    if expiry.isdigit():
        return int(expiry)
    import re
    m = re.match(r"^(\d+)([smhd])$", expiry)
    if not m:
        return 900
    n, u = int(m.group(1)), m.group(2)
    return {"s": n, "m": n * 60, "h": n * 3600, "d": n * 86400}[u]

def generate_access_token(payload: JWTPayload) -> str:
    secrets = get_jwt_secrets()
    expires = _expiry("JWT_EXPIRES_IN", "45m")
    return jwt.encode(
        {**payload, "exp": int(time.time()) + _to_seconds(expires)},
        secrets.JWT_SECRET,
        algorithm="HS256",
        headers={"typ": "JWT"},
    )

def verify_access_token(token: str) -> JWTPayload:
    secrets = get_jwt_secrets()
    return jwt.decode(token, secrets.JWT_SECRET, algorithms=["HS256"], audience="arcforge-client", issuer="arcforge-api", options={"verify_aud": False, "verify_iss": False})

def generate_refresh_token(payload: JWTPayload) -> str:
    secrets = get_jwt_secrets()
    expires = _expiry("JWT_REFRESH_EXPIRES_IN", "7d")
    return jwt.encode(
        {**payload, "exp": int(time.time()) + _to_seconds(expires)},
        secrets.JWT_REFRESH_SECRET,
        algorithm="HS256",
    )

def verify_refresh_token(token: str) -> JWTPayload:
    secrets = get_jwt_secrets()
    return jwt.decode(token, secrets.JWT_REFRESH_SECRET, algorithms=["HS256"], options={"verify_aud": False, "verify_iss": False})

def generate_tokens(payload: JWTPayload) -> dict[str, Any]:
    access = generate_access_token(payload)
    refresh = generate_refresh_token(payload)
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "expiresIn": _to_seconds(_expiry("JWT_EXPIRES_IN", "45m")),
        "refreshExpiresIn": _to_seconds(_expiry("JWT_REFRESH_EXPIRES_IN", "7d")),
    }
