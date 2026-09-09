"""LinkedIn OpenID Connect helpers for *login* (identity only).

Completely separate from publishing OAuth in publishing_controller
(/api/social/linkedin/* + SocialAccount). Login scopes exclude publish permissions.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils.linkedin_oidc_secrets import (
    get_linkedin_oidc_secrets,
    linkedin_oidc_redirect_uri,
)

# Identity-only — never include w_member_social / org publish scopes here
LINKEDIN_OIDC_SCOPES = "openid profile email"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def build_linkedin_oidc_authorize_url(*, state: str, nonce: str) -> str:
    secrets = get_linkedin_oidc_secrets()
    if not secrets.client_id:
        raise ValueError("LINKEDIN_OIDC_CLIENT_ID is not configured")
    params = {
        "response_type": "code",
        "client_id": secrets.client_id,
        "redirect_uri": linkedin_oidc_redirect_uri(),
        "state": state,
        "scope": LINKEDIN_OIDC_SCOPES,
        "nonce": nonce,
    }
    return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"


def exchange_linkedin_oidc_code(code: str) -> dict[str, Any]:
    secrets = get_linkedin_oidc_secrets()
    if not secrets.client_id or not secrets.client_secret:
        raise ValueError("LinkedIn OIDC client credentials are not configured")
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": secrets.client_id,
            "client_secret": secrets.client_secret,
            "redirect_uri": linkedin_oidc_redirect_uri(),
        }
    ).encode("utf-8")
    req = Request(
        LINKEDIN_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=20) as resp:  # noqa: S310 — fixed LinkedIn HTTPS endpoint
        return json.loads(resp.read().decode("utf-8"))


def fetch_linkedin_oidc_userinfo(access_token: str) -> dict[str, Any]:
    req = Request(
        LINKEDIN_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))
