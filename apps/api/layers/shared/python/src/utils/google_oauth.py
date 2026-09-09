"""Google OAuth login helpers (token exchange + identity)."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils.google_oauth_secrets import (
    get_google_oauth_secrets,
    google_redirect_uri,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def build_google_authorize_url(*, state: str) -> str:
    secrets = get_google_oauth_secrets()
    if not secrets.client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")
    params = {
        "client_id": secrets.client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_google_code(code: str) -> dict[str, Any]:
    secrets = get_google_oauth_secrets()
    if not secrets.client_id or not secrets.client_secret:
        raise ValueError("Google OAuth client credentials are not configured")
    body = urlencode(
        {
            "code": code,
            "client_id": secrets.client_id,
            "client_secret": secrets.client_secret,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = Request(
        GOOGLE_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=20) as resp:  # noqa: S310 — fixed Google HTTPS endpoint
        return json.loads(resp.read().decode("utf-8"))


def fetch_google_userinfo(access_token: str) -> dict[str, Any]:
    req = Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))
