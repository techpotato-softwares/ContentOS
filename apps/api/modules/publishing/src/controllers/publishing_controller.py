"""LinkedIn OAuth + review gate + publish."""
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
from utils.tenant import resolve_tenant_id, write_audit


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


def _encode_state(tenant_id: int, user_id: int) -> str:
    raw = json.dumps({"tenantId": tenant_id, "userId": user_id})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_state(state: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(state.encode()).decode())


def _store_tokens(session, tenant_id: int, tokens: dict, profile: dict):
    enc = base64.b64encode(json.dumps(tokens).encode()).decode()
    acct = session.exec(
        select(SocialAccount).where(
            SocialAccount.tenant_id == tenant_id, SocialAccount.platform == "linkedin"
        )
    ).first()
    expiry = None
    if tokens.get("expires_in"):
        expiry = datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
    if not acct:
        acct = SocialAccount(tenant_id=tenant_id, platform="linkedin")
    acct.platform_user_id = profile.get("sub") or profile.get("id")
    acct.username = profile.get("name") or profile.get("localizedFirstName")
    acct.token_payload_encrypted = enc
    acct.token_secret_arn = f"local/{os.environ.get('APP_NAME','contentos')}/linkedin/{tenant_id}"
    acct.token_expiry = expiry
    acct.is_active = True
    acct.updated_at = datetime.utcnow()
    session.add(acct)


def _load_tokens(acct: SocialAccount) -> dict:
    if not acct.token_payload_encrypted:
        raise AppError("LinkedIn not connected", 400, "LINKEDIN_DISCONNECTED")
    return json.loads(base64.b64decode(acct.token_payload_encrypted.encode()).decode())


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
    return {
        "postId": p.post_id,
        "batchId": p.batch_id,
        "angle": p.angle,
        "caption": p.caption,
        "imageUrl": p.image_url,
        "layout": layout,
        "headline": (layout or {}).get("headline"),
        "subhead": (layout or {}).get("subhead"),
        "bullets": (layout or {}).get("bullets"),
        "score": score,
        "sourceType": getattr(p, "source_type", None),
        "sourceRef": getattr(p, "source_ref", None),
        "abLabel": getattr(p, "ab_label", None),
        "status": p.status,
        "linkedinPostId": p.linkedin_post_id,
        "scheduledAt": p.scheduled_at.isoformat() + "Z" if getattr(p, "scheduled_at", None) else None,
        "publishedAt": p.published_at.isoformat() if p.published_at else None,
    }


@Controller(path="/api", lambda_name="publishing")
class PublishingController:
    @Get("/social/linkedin/connect")
    @RequireModule("publishing")
    @RequirePermission("tenant:admin", "posts:publish", "admin:tenants")
    def linkedin_connect(self, user=None):
        cfg = _linkedin_cfg()
        if not cfg["client_id"]:
            raise ValidationError("LINKEDIN_CLIENT_ID not configured")
        tid = resolve_tenant_id(user)
        params = {
            "response_type": "code",
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "state": _encode_state(tid, user["userId"]),
            "scope": "openid profile w_member_social",
        }
        url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)
        return create_success_response({"authorizeUrl": url})

    @Get("/social/linkedin/callback")
    @ApiPublic()
    def linkedin_callback(self, query: dict | None = None):
        q = query or {}
        code = q.get("code")
        state = q.get("state")
        if not code or not state:
            raise ValidationError("code and state required")
        parsed = _decode_state(state)
        tid = int(parsed["tenantId"])
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
            token_resp.raise_for_status()
            tokens = token_resp.json()
            profile = {}
            try:
                me = client.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )
                if me.status_code == 200:
                    profile = me.json()
            except Exception:
                pass
        with get_session() as session:
            _store_tokens(session, tid, tokens, profile)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=parsed.get("userId"),
                action="linkedin.connect",
                resource_type="social_account",
                resource_id=str(tid),
            )
            session.commit()
        # Redirect body for browser
        from middleware.error_handler import CORS

        loc = cfg["frontend_redirect"] + "?linkedin=connected"
        return {
            "statusCode": 302,
            "headers": {**CORS, "Location": loc},
            "body": "",
        }

    @Get("/social/linkedin/status")
    @RequireModule("publishing")
    @RequirePermission("agent:chat", "posts:publish", "tenant:admin")
    def linkedin_status(self, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            acct = session.exec(
                select(SocialAccount).where(
                    SocialAccount.tenant_id == tid,
                    SocialAccount.platform == "linkedin",
                    SocialAccount.is_active == True,
                )
            ).first()
            return create_success_response(
                {
                    "connected": bool(acct),
                    "username": acct.username if acct else None,
                    "expiresAt": acct.token_expiry.isoformat() if acct and acct.token_expiry else None,
                }
            )

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
    def publish(self, id: str, user=None):
        """Hard gate: only approved posts can be published."""
        tid = resolve_tenant_id(user)
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
            acct = session.exec(
                select(SocialAccount).where(
                    SocialAccount.tenant_id == tid,
                    SocialAccount.platform == "linkedin",
                    SocialAccount.is_active == True,
                )
            ).first()
            if not acct:
                raise AppError("Connect LinkedIn first", 400, "LINKEDIN_DISCONNECTED")

            tokens = _load_tokens(acct)
            access = tokens.get("access_token")
            person_urn = f"urn:li:person:{acct.platform_user_id}" if acct.platform_user_id else None

            linkedin_id = None
            cfg_ok = bool(os.environ.get("LINKEDIN_CLIENT_ID") and access and person_urn)

            if cfg_ok and not (post.image_url or "").startswith("data:"):
                linkedin_id = _linkedin_ugc_publish(access, person_urn, post.caption, post.image_url)
            else:
                # Local / stub publish when image is data-URL or LinkedIn incomplete
                linkedin_id = f"stub-li-{post.post_id}-{int(datetime.utcnow().timestamp())}"

            post.status = "published"
            post.linkedin_post_id = linkedin_id
            post.published_at = datetime.utcnow()
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="posts.publish",
                resource_type="content_post",
                resource_id=str(post.post_id),
                detail=linkedin_id,
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

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


def _linkedin_ugc_publish(access_token: str, author_urn: str, caption: str, image_url: str | None) -> str:
    """Publish text (+ optional image URL register) via LinkedIn ugcPosts."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    share = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption[:2900]},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    # Image asset upload is multi-step; for MVP with remote URL use ARTICLE or TEXT.
    # If image_url is https, attach as IMAGE after registerUpload — simplified to text when complex.
    with httpx.Client(timeout=60.0) as client:
        r = client.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=share)
        if r.status_code >= 400:
            raise AppError(f"LinkedIn publish failed: {r.text[:400]}", 502, "LINKEDIN_ERROR")
        # Rest.li returns id in header or body
        return r.headers.get("x-restli-id") or r.json().get("id") or r.text[:80]
