"""LinkedIn OAuth (member + company page) + review gate + publish."""
from __future__ import annotations
import base64
import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
import httpx
from sqlmodel import select
from decorators import Controller, Get, Post
from decorators.auth_decorators import RequirePermission, RequireModule, ApiPublic
from database import get_session
from database.models import ContentPost, SocialAccount
from middleware.error_handler import NotFoundError, ValidationError, AppError, create_success_response
from utils.tenant import resolve_tenant_id, write_audit, is_super_admin
from modules.publishing.src.linkedin_client import (
    carousel_capability,
    execute_linkedin_publish,
    map_linkedin_http_error,
)


MEMBER_SCOPES = "openid profile w_member_social"
ORG_SCOPES = (
    "openid profile w_member_social w_organization_social r_organization_admin"
)
POSTABLE_ORG_ROLES = {
    "ADMINISTRATOR",
    "CONTENT_ADMIN",
    "DIRECT_SPONSORED_CONTENT_POSTER",
}


def _ensure_social_account_columns():
    """Add dual-account columns / unique constraint on existing DBs."""
    try:
        from sqlalchemy import text
        from database import get_engine

        with get_engine().begin() as conn:
            for name, typ in [
                ("account_kind", "VARCHAR DEFAULT 'member'"),
                ("author_urn", "VARCHAR"),
                ("metadata_json", "TEXT"),
            ]:
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS {name} {typ}"
                        )
                    )
                except Exception:
                    pass
            try:
                conn.execute(
                    text(
                        "UPDATE social_accounts SET account_kind = 'member' "
                        "WHERE account_kind IS NULL OR account_kind = ''"
                    )
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text(
                        "UPDATE social_accounts SET author_urn = "
                        "CASE WHEN platform_user_id IS NOT NULL AND platform_user_id <> '' "
                        "THEN 'urn:li:person:' || platform_user_id ELSE author_urn END "
                        "WHERE (author_urn IS NULL OR author_urn = '') "
                        "AND (account_kind = 'member' OR account_kind IS NULL)"
                    )
                )
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE social_accounts DROP CONSTRAINT IF EXISTS uq_tenant_platform"))
            except Exception:
                pass
            try:
                conn.execute(
                    text(
                        "ALTER TABLE social_accounts DROP CONSTRAINT IF EXISTS uq_tenant_platform_kind"
                    )
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text(
                        "ALTER TABLE social_accounts ADD CONSTRAINT uq_tenant_platform_kind "
                        "UNIQUE (tenant_id, platform, account_kind)"
                    )
                )
            except Exception:
                pass
    except Exception:
        pass


def _linkedin_cfg():
    return {
        "client_id": os.environ.get("LINKEDIN_CLIENT_ID", ""),
        "client_secret": os.environ.get("LINKEDIN_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get(
            "LINKEDIN_REDIRECT_URI", "http://localhost:4001/api/social/linkedin/callback"
        ),
        "frontend_redirect": os.environ.get(
            "LINKEDIN_FRONTEND_REDIRECT", "http://localhost:5173/connections/linkedin"
        ),
    }


def _encode_state(tenant_id: int, user_id: int, mode: str = "member") -> str:
    raw = json.dumps({"tenantId": tenant_id, "userId": user_id, "mode": mode})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_state(state: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(state.encode()).decode())


def _meta(acct: SocialAccount | None) -> dict:
    if not acct or not acct.metadata_json:
        return {}
    try:
        return json.loads(acct.metadata_json)
    except Exception:
        return {}


def _set_meta(acct: SocialAccount, data: dict):
    acct.metadata_json = json.dumps(data)


def _user_perms(user: dict | None) -> set:
    return set((user or {}).get("permissions") or [])


def _is_tenant_admin(user: dict | None) -> bool:
    perms = _user_perms(user)
    return is_super_admin(user) or "tenant:admin" in perms or "admin:tenants" in perms


def _resolve_tid(user, query: dict | None = None, data: dict | None = None) -> int:
    requested = None
    for src in (query or {}, data or {}):
        raw = src.get("tenantId")
        if raw is not None and str(raw).strip() != "":
            requested = int(raw)
            break
    return resolve_tenant_id(user, requested)


def _get_account(session, tenant_id: int, kind: str, active_only: bool = False):
    q = select(SocialAccount).where(
        SocialAccount.tenant_id == tenant_id,
        SocialAccount.platform == "linkedin",
        SocialAccount.account_kind == kind,
    )
    if active_only:
        q = q.where(SocialAccount.is_active == True)  # noqa: E712
    return session.exec(q).first()


def _account_status(acct: SocialAccount | None) -> dict:
    if not acct or not acct.is_active:
        return {"connected": False}
    meta = _meta(acct)
    pending = bool(meta.get("pendingSelection"))
    return {
        "connected": bool(acct.author_urn) and not pending,
        "pendingSelection": pending,
        "username": acct.username,
        "platformUserId": acct.platform_user_id,
        "authorUrn": acct.author_urn,
        "expiresAt": acct.token_expiry.isoformat() if acct.token_expiry else None,
        "metadata": {
            k: meta.get(k)
            for k in ("vanityName", "logoUrl", "organizationName")
            if meta.get(k)
        },
    }


def _store_tokens(
    session,
    tenant_id: int,
    tokens: dict,
    *,
    account_kind: str,
    platform_user_id: str | None,
    username: str | None,
    author_urn: str | None,
    metadata: dict | None = None,
    is_active: bool = True,
):
    enc = base64.b64encode(json.dumps(tokens).encode()).decode()
    acct = _get_account(session, tenant_id, account_kind)
    expiry = None
    if tokens.get("expires_in"):
        expiry = datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
    if not acct:
        acct = SocialAccount(
            tenant_id=tenant_id,
            platform="linkedin",
            account_kind=account_kind,
        )
    acct.platform_user_id = platform_user_id
    acct.username = username
    acct.author_urn = author_urn
    acct.token_payload_encrypted = enc
    acct.token_secret_arn = (
        f"local/{os.environ.get('APP_NAME', 'contentos')}/linkedin/{account_kind}/{tenant_id}"
    )
    acct.token_expiry = expiry
    acct.is_active = is_active
    acct.updated_at = datetime.utcnow()
    if metadata is not None:
        _set_meta(acct, metadata)
    session.add(acct)
    return acct


def _load_tokens(acct: SocialAccount) -> dict:
    if not acct.token_payload_encrypted:
        raise AppError("LinkedIn not connected", 400, "LINKEDIN_DISCONNECTED")
    return json.loads(base64.b64decode(acct.token_payload_encrypted.encode()).decode())


def _person_id_from_profile(profile: dict, access_token: str) -> str | None:
    """Prefer classic member id for urn:li:person; fall back to OIDC sub."""
    try:
        with httpx.Client(timeout=20.0) as client:
            me = client.get(
                "https://api.linkedin.com/v2/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
            if me.status_code == 200:
                mid = me.json().get("id")
                if mid:
                    return str(mid)
    except Exception:
        pass
    for key in ("id", "sub"):
        val = profile.get(key)
        if val and isinstance(val, str) and not val.startswith("urn:"):
            return val
    return None


def _post_dict(p: ContentPost) -> dict:
    layout = None
    if getattr(p, "layout_json", None):
        try:
            layout = json.loads(p.layout_json)
        except Exception:
            layout = None
    score = None
    if getattr(p, "score_json", None):
        try:
            score = json.loads(p.score_json)
        except Exception:
            score = None
    fmt = (layout or {}).get("format") or ("text" if not p.image_url else "image")
    return {
        "postId": p.post_id,
        "batchId": p.batch_id,
        "angle": p.angle,
        "caption": p.caption,
        "imageUrl": p.image_url,
        "layout": layout,
        "format": fmt,
        "headline": (layout or {}).get("headline"),
        "subhead": (layout or {}).get("subhead"),
        "bullets": (layout or {}).get("bullets"),
        "slides": (layout or {}).get("slides"),
        "hashtags": (layout or {}).get("hashtags"),
        "attachedImage": bool(
            (layout or {}).get("attachedImage")
            or ((layout or {}).get("format") == "text" and p.image_url)
        ),
        "score": score,
        "sourceType": getattr(p, "source_type", None),
        "sourceRef": getattr(p, "source_ref", None),
        "abLabel": getattr(p, "ab_label", None),
        "status": p.status,
        "linkedinPostId": p.linkedin_post_id,
        "scheduledAt": p.scheduled_at.isoformat() + "Z" if getattr(p, "scheduled_at", None) else None,
        "publishedAt": p.published_at.isoformat() if p.published_at else None,
    }


def _pick_publish_account(session, tid: int, publish_as: str | None):
    member = _get_account(session, tid, "member", active_only=True)
    org = _get_account(session, tid, "organization", active_only=True)
    org_ready = org and org.author_urn and not _meta(org).get("pendingSelection")
    member_ready = member and member.author_urn and member.token_payload_encrypted

    kind = (publish_as or "").strip().lower()
    if kind in ("member", "organization"):
        acct = org if kind == "organization" else member
        if kind == "organization" and not org_ready:
            raise AppError(
                "Company page not connected or page not selected",
                400,
                "LINKEDIN_ORG_NOT_READY",
            )
        if kind == "member" and not member_ready:
            raise AppError("Connect LinkedIn personal profile first", 400, "LINKEDIN_DISCONNECTED")
        return acct, kind

    if org_ready:
        return org, "organization"
    if member_ready:
        return member, "member"
    raise AppError("Connect LinkedIn first", 400, "LINKEDIN_DISCONNECTED")


@Controller(path="/api", lambda_name="publishing")
class PublishingController:
    @Get("/social/linkedin/connect")
    @RequireModule("publishing")
    @RequirePermission("tenant:admin", "posts:publish", "admin:tenants")
    def linkedin_connect(self, user=None, query: dict | None = None):
        _ensure_social_account_columns()
        cfg = _linkedin_cfg()
        if not cfg["client_id"]:
            raise ValidationError("LINKEDIN_CLIENT_ID not configured")
        q = query or {}
        mode = (q.get("mode") or "member").strip().lower()
        if mode not in ("member", "organization"):
            raise ValidationError("mode must be member or organization")
        if mode == "organization" and not _is_tenant_admin(user):
            raise AppError(
                "Only tenant admin or super admin can connect a company page",
                403,
                "FORBIDDEN",
            )
        if mode == "member" and not (
            _user_perms(user) & {"posts:publish", "tenant:admin", "admin:tenants"}
        ):
            raise AppError("Missing permission to connect LinkedIn", 403, "FORBIDDEN")

        tid = _resolve_tid(user, q)
        scopes = ORG_SCOPES if mode == "organization" else MEMBER_SCOPES
        params = {
            "response_type": "code",
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "state": _encode_state(tid, user["userId"], mode),
            "scope": scopes,
        }
        url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)
        return create_success_response({"authorizeUrl": url, "mode": mode})

    @Get("/social/linkedin/callback")
    @ApiPublic()
    def linkedin_callback(self, query: dict | None = None):
        _ensure_social_account_columns()
        q = query or {}
        code = q.get("code")
        state = q.get("state")
        if not code or not state:
            raise ValidationError("code and state required")
        parsed = _decode_state(state)
        tid = int(parsed["tenantId"])
        mode = (parsed.get("mode") or "member").strip().lower()
        if mode not in ("member", "organization"):
            mode = "member"
        cfg = _linkedin_cfg()
        with httpx.Client(timeout=30.0) as client:
            token_resp = client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": cfg["redirect_uri"],
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code >= 400 and mode == "organization":
                # Likely missing Community Management product / scopes
                from middleware.error_handler import CORS

                loc = (
                    cfg["frontend_redirect"]
                    + "?linkedin=error&code=LINKEDIN_ORG_SCOPES_UNAVAILABLE"
                )
                return {
                    "statusCode": 302,
                    "headers": {**CORS, "Location": loc},
                    "body": "",
                }
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access = tokens.get("access_token") or ""
            profile = {}
            try:
                me = client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {access}"},
                )
                if me.status_code == 200:
                    profile = me.json()
            except Exception:
                pass

        from middleware.error_handler import CORS

        with get_session() as session:
            if mode == "organization":
                _store_tokens(
                    session,
                    tid,
                    tokens,
                    account_kind="organization",
                    platform_user_id=None,
                    username=profile.get("name") or "Company page (select)",
                    author_urn=None,
                    metadata={
                        "pendingSelection": True,
                        "connectedByUserId": parsed.get("userId"),
                        "memberName": profile.get("name"),
                    },
                    is_active=True,
                )
                write_audit(
                    session,
                    tenant_id=tid,
                    actor_user_id=parsed.get("userId"),
                    action="linkedin.connect.organization",
                    resource_type="social_account",
                    resource_id=str(tid),
                )
                session.commit()
                loc = cfg["frontend_redirect"] + "?linkedin=select_page"
            else:
                person_id = _person_id_from_profile(profile, access)
                author_urn = f"urn:li:person:{person_id}" if person_id else None
                _store_tokens(
                    session,
                    tid,
                    tokens,
                    account_kind="member",
                    platform_user_id=person_id,
                    username=profile.get("name") or profile.get("localizedFirstName"),
                    author_urn=author_urn,
                    metadata={"connectedByUserId": parsed.get("userId")},
                    is_active=True,
                )
                write_audit(
                    session,
                    tenant_id=tid,
                    actor_user_id=parsed.get("userId"),
                    action="linkedin.connect.member",
                    resource_type="social_account",
                    resource_id=str(tid),
                )
                session.commit()
                loc = cfg["frontend_redirect"] + "?linkedin=connected&mode=member"

        return {
            "statusCode": 302,
            "headers": {**CORS, "Location": loc},
            "body": "",
        }

    @Get("/social/linkedin/status")
    @RequireModule("publishing")
    @RequirePermission("agent:chat", "posts:publish", "tenant:admin")
    def linkedin_status(self, user=None, query: dict | None = None):
        _ensure_social_account_columns()
        tid = _resolve_tid(user, query)
        with get_session() as session:
            member = _get_account(session, tid, "member")
            org = _get_account(session, tid, "organization")
            member_st = _account_status(member)
            org_st = _account_status(org)
            # Backward-compatible flat fields (prefer org if fully connected else member)
            primary = org_st if org_st.get("connected") else member_st
            return create_success_response(
                {
                    "member": member_st,
                    "organization": org_st,
                    "connected": bool(primary.get("connected")),
                    "username": primary.get("username"),
                    "expiresAt": primary.get("expiresAt"),
                    "carousel": carousel_capability(),
                }
            )

    @Get("/social/linkedin/organizations")
    @RequireModule("publishing")
    @RequirePermission("tenant:admin", "admin:tenants")
    def linkedin_organizations(self, user=None, query: dict | None = None):
        _ensure_social_account_columns()
        tid = _resolve_tid(user, query)
        with get_session() as session:
            acct = _get_account(session, tid, "organization", active_only=True)
            if not acct or not acct.token_payload_encrypted:
                raise AppError(
                    "Connect company page OAuth first",
                    400,
                    "LINKEDIN_ORG_NOT_CONNECTED",
                )
            tokens = _load_tokens(acct)
            access = tokens.get("access_token")
        pages = _list_organization_pages(access)
        return create_success_response({"organizations": pages})

    @Post("/social/linkedin/organizations/select")
    @RequireModule("publishing")
    @RequirePermission("tenant:admin", "admin:tenants")
    def linkedin_select_organization(self, data: dict | None = None, user=None):
        _ensure_social_account_columns()
        data = data or {}
        tid = _resolve_tid(user, data=data)
        org_id = str(data.get("organizationId") or data.get("id") or "").strip()
        if not org_id:
            raise ValidationError("organizationId is required")
        org_id = org_id.replace("urn:li:organization:", "")
        name = (data.get("name") or data.get("organizationName") or "").strip() or None
        vanity = (data.get("vanityName") or "").strip() or None

        with get_session() as session:
            acct = _get_account(session, tid, "organization", active_only=True)
            if not acct or not acct.token_payload_encrypted:
                raise AppError(
                    "Connect company page OAuth first",
                    400,
                    "LINKEDIN_ORG_NOT_CONNECTED",
                )
            meta = _meta(acct)
            meta["pendingSelection"] = False
            meta["organizationName"] = name
            meta["vanityName"] = vanity
            meta["selectedAt"] = datetime.utcnow().isoformat() + "Z"
            acct.platform_user_id = org_id
            acct.username = name or f"Org {org_id}"
            acct.author_urn = f"urn:li:organization:{org_id}"
            acct.is_active = True
            acct.updated_at = datetime.utcnow()
            _set_meta(acct, meta)
            session.add(acct)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="linkedin.select_organization",
                resource_type="social_account",
                resource_id=org_id,
                detail=name,
            )
            session.commit()
            session.refresh(acct)
            return create_success_response(_account_status(acct))

    @Post("/social/linkedin/disconnect")
    @RequireModule("publishing")
    @RequirePermission("tenant:admin", "posts:publish", "admin:tenants")
    def linkedin_disconnect(self, data: dict | None = None, user=None):
        _ensure_social_account_columns()
        data = data or {}
        kind = (data.get("accountKind") or data.get("mode") or "member").strip().lower()
        if kind not in ("member", "organization"):
            raise ValidationError("accountKind must be member or organization")
        if kind == "organization" and not _is_tenant_admin(user):
            raise AppError(
                "Only tenant admin or super admin can disconnect a company page",
                403,
                "FORBIDDEN",
            )
        tid = _resolve_tid(user, data=data)
        with get_session() as session:
            acct = _get_account(session, tid, kind)
            if not acct:
                return create_success_response({"disconnected": True, "accountKind": kind})
            acct.is_active = False
            acct.token_payload_encrypted = None
            acct.author_urn = None
            acct.platform_user_id = None
            acct.updated_at = datetime.utcnow()
            _set_meta(acct, {})
            session.add(acct)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="linkedin.disconnect",
                resource_type="social_account",
                resource_id=kind,
            )
            session.commit()
            return create_success_response({"disconnected": True, "accountKind": kind})

    @Get("/posts")
    @RequireModule("publishing")
    @RequirePermission("posts:review", "agent:chat", "posts:publish")
    def list_posts(self, user=None, query: dict | None = None):
        tid = resolve_tenant_id(user)
        status = (query or {}).get("status")
        with get_session() as session:
            q = select(ContentPost).where(ContentPost.tenant_id == tid)
            if status:
                q = q.where(ContentPost.status == status)
            q = q.order_by(ContentPost.created_at.desc())
            rows = session.exec(q).all()
            return create_success_response([_post_dict(p) for p in rows])

    @Post("/posts/{id}/submit-review")
    @RequireModule("publishing")
    @RequirePermission("posts:review", "agent:chat")
    def submit_review(self, id: str, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            if post.status not in ("draft", "rejected"):
                raise ValidationError(f"Cannot submit from status {post.status}")
            post.status = "pending_review"
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="posts.submit_review",
                resource_type="content_post",
                resource_id=str(post.post_id),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

    @Post("/posts/{id}/approve")
    @RequireModule("publishing")
    @RequirePermission("posts:review")
    def approve(self, id: str, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            if post.status not in ("pending_review", "draft"):
                raise ValidationError(f"Cannot approve from status {post.status}")
            post.status = "approved"
            post.reviewed_by = user["userId"]
            post.reviewed_at = datetime.utcnow()
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="posts.approve",
                resource_type="content_post",
                resource_id=str(post.post_id),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

    @Post("/posts/{id}/reject")
    @RequireModule("publishing")
    @RequirePermission("posts:review")
    def reject(self, id: str, data: dict | None = None, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            post.status = "rejected"
            post.reviewed_by = user["userId"]
            post.reviewed_at = datetime.utcnow()
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="posts.reject",
                resource_type="content_post",
                resource_id=str(post.post_id),
                detail=(data or {}).get("reason"),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

    @Post("/posts/{id}/publish")
    @RequireModule("publishing")
    @RequirePermission("posts:publish")
    def publish(self, id: str, data: dict | None = None, user=None):
        """Hard gate: only approved posts can be published."""
        _ensure_social_account_columns()
        tid = resolve_tenant_id(user)
        data = data or {}
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            if post.status != "approved":
                raise AppError(
                    "Post must be approved before publishing",
                    400,
                    "REVIEW_REQUIRED",
                )
            acct, kind = _pick_publish_account(session, tid, data.get("publishAs"))
            tokens = _load_tokens(acct)
            access = tokens.get("access_token")
            author_urn = acct.author_urn
            if not author_urn:
                raise AppError(
                    "LinkedIn author URN missing — reconnect under Connections → LinkedIn.",
                    400,
                    "LINKEDIN_RECONNECT_REQUIRED",
                )

            layout = None
            if post.layout_json:
                try:
                    layout = json.loads(post.layout_json)
                except Exception:
                    layout = None
            fmt = (layout or {}).get("format") or ("text" if not post.image_url else "image")

            allow_stub = os.environ.get("IS_LOCAL") == "true" and not os.environ.get(
                "LINKEDIN_CLIENT_ID"
            )
            linkedin_id = execute_linkedin_publish(
                access_token=access or "",
                author_urn=author_urn,
                caption=post.caption or "",
                image_url=post.image_url,
                layout=layout,
                allow_stub=allow_stub,
            )

            post.status = "published"
            post.linkedin_post_id = linkedin_id
            post.published_at = datetime.utcnow()
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="linkedin.publish",
                resource_type="content_post",
                resource_id=str(post.post_id),
                detail=json.dumps({"linkedinId": linkedin_id, "publishAs": kind, "format": fmt}),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

    @Post("/posts/{id}/quick-publish")
    @RequireModule("publishing")
    @RequirePermission("posts:publish")
    def quick_publish(self, id: str, data: dict | None = None, user=None):
        """One-click: approve (if needed) then publish to LinkedIn — ideal for research text posts."""
        _ensure_social_account_columns()
        tid = resolve_tenant_id(user)
        data = data or {}
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            if post.status == "published":
                return create_success_response(_post_dict(post))
            if post.status == "rejected":
                raise ValidationError("Cannot publish a rejected post — regenerate or restore first")
            if post.status in ("draft", "pending_review"):
                post.status = "approved"
                post.reviewed_by = user["userId"]
                post.reviewed_at = datetime.utcnow()
                post.updated_at = datetime.utcnow()
                session.add(post)
                write_audit(
                    session,
                    tenant_id=tid,
                    actor_user_id=user["userId"],
                    action="posts.approve",
                    resource_type="content_post",
                    resource_id=str(post.post_id),
                    detail="quick_publish",
                )
                session.commit()
                session.refresh(post)
        # Reuse publish gate
        return self.publish(id, data=data, user=user)

    @Post("/posts/{id}/schedule")
    @RequireModule("publishing")
    @RequirePermission("posts:review", "posts:publish")
    def schedule_post(self, id: str, data: dict | None = None, user=None):
        """Set or clear scheduled_at / ab_label on a post."""
        tid = resolve_tenant_id(user)
        data = data or {}
        with get_session() as session:
            post = session.get(ContentPost, int(id))
            if not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            if post.status == "published":
                raise ValidationError("Cannot reschedule a published post")
            raw = data.get("scheduledAt")
            if raw in (None, "", False):
                post.scheduled_at = None
            else:
                try:
                    post.scheduled_at = datetime.fromisoformat(
                        str(raw).replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception as e:
                    raise ValidationError(f"Invalid scheduledAt: {e}")
            if "abLabel" in data:
                label = data.get("abLabel")
                post.ab_label = str(label)[:16] if label else None
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="posts.schedule",
                resource_type="content_post",
                resource_id=str(post.post_id),
                detail=str(post.scheduled_at),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))


def _list_organization_pages(access_token: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": os.environ.get("LINKEDIN_API_VERSION", "202506"),
    }
    pages: list[dict] = []
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            "https://api.linkedin.com/rest/organizationAcls",
            params={"q": "roleAssignee", "count": 50, "start": 0},
            headers=headers,
        )
        if r.status_code >= 400:
            # Fallback legacy path
            r = client.get(
                "https://api.linkedin.com/v2/organizationAcls",
                params={"q": "roleAssignee", "count": 50},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
            )
        if r.status_code >= 400:
            raise map_linkedin_http_error(
                r.status_code,
                r.text,
                default_code="LINKEDIN_ORG_SCOPES_UNAVAILABLE",
                context="list organizations",
            )
        elements = r.json().get("elements") or []
        for el in elements:
            role = (el.get("role") or "").upper()
            state = (el.get("state") or "").upper()
            if state and state != "APPROVED":
                continue
            if role and role not in POSTABLE_ORG_ROLES:
                continue
            org_urn = el.get("organization") or ""
            org_id = str(org_urn).replace("urn:li:organization:", "")
            if not org_id:
                continue
            name = None
            vanity = None
            try:
                org_r = client.get(
                    f"https://api.linkedin.com/rest/organizations/{org_id}",
                    headers=headers,
                )
                if org_r.status_code >= 400:
                    org_r = client.get(
                        f"https://api.linkedin.com/v2/organizations/{org_id}",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "X-Restli-Protocol-Version": "2.0.0",
                        },
                    )
                if org_r.status_code == 200:
                    oj = org_r.json()
                    name = (
                        oj.get("localizedName")
                        or (oj.get("name") or {}).get("localized", {}).get("en_US")
                        or oj.get("vanityName")
                    )
                    vanity = oj.get("vanityName")
            except Exception:
                pass
            pages.append(
                {
                    "organizationId": org_id,
                    "organizationUrn": f"urn:li:organization:{org_id}",
                    "name": name or f"Organization {org_id}",
                    "vanityName": vanity,
                    "role": role,
                }
            )
    # Dedupe by org id
    seen = set()
    out = []
    for p in pages:
        if p["organizationId"] in seen:
            continue
        seen.add(p["organizationId"])
        out.append(p)
    return out


# Re-exports for scheduled_publisher / tests
from modules.publishing.src.linkedin_client import (  # noqa: E402
    linkedin_document_publish as _linkedin_document_publish,
    linkedin_ugc_publish as _linkedin_ugc_publish,
)
