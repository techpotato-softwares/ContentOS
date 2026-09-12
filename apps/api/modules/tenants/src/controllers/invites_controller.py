"""Tenant team invite APIs — create/list/revoke (admin) + accept (public)."""
from __future__ import annotations

import json
from datetime import datetime

from passlib.hash import bcrypt
from sqlmodel import select

from database import get_session
from database.models import Tenant, TenantInvite, User
from decorators import Controller, Delete, Get, Post
from decorators.auth_decorators import ApiPublic, RequireModule, RequirePermission
from middleware.auth import auth_middleware
from middleware.error_handler import (
    AppError,
    ConflictError,
    NotFoundError,
    ValidationError,
    create_success_response,
)
from utils.tenant import require_user, resolve_tenant_id, write_audit
from utils.tenant_invites import (
    accept_invite_for_user,
    assert_invite_email_matches,
    create_or_refresh_invite,
    get_role_by_name,
    invite_public,
    load_invite_by_raw_token,
    mark_expired_if_needed,
    send_invite_email,
)
from utils.webtoken import generate_tokens


def _optional_user(event: dict | None) -> dict | None:
    if not event:
        return None
    headers = event.get("headers") or {}
    auth = headers.get("Authorization") or headers.get("authorization")
    if not auth:
        return None
    result = auth_middleware(event)
    if isinstance(result, dict) and result.get("user"):
        return result["user"]
    return None


def _session_tokens_for_user(session, user: User) -> dict:
    from modules.platform.src.controllers.auth_controller import (
        _auth_user_dict,
        _modules_for_tenant,
        _token_payload,
        _user_permissions,
    )

    role, permissions = _user_permissions(session, user.role_id)
    modules = _modules_for_tenant(session, user.tenant_id)
    tokens = generate_tokens(_token_payload(user, role, permissions, modules))
    return {
        **tokens,
        "user": _auth_user_dict(user, role, permissions, modules),
    }


@Controller(path="/api", lambda_name="tenants")
class InvitesController:
    @Post("/tenants/invites")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin")
    def create_invite(self, data: dict, user=None):
        require_user(user)
        data = data or {}
        email = (data.get("email") or "").strip()
        role = data.get("role") or "tenant_member"
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            invite, raw_token = create_or_refresh_invite(
                session,
                tenant=tenant,
                email=email,
                role=role,
                invited_by=user.get("userId"),
            )
            session.flush()
            mail = send_invite_email(
                tenant=tenant,
                invite=invite,
                raw_token=raw_token,
                inviter_name=user.get("username") or user.get("email"),
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="invite.create",
                resource_type="tenant_invite",
                resource_id=str(invite.invite_id),
                detail=json.dumps(
                    {
                        "email": invite.email,
                        "role": invite.role,
                        "emailSent": bool(mail.get("sent")),
                    }
                ),
            )
            session.commit()
            session.refresh(invite)
            # Raw token never returned — only email delivery carries the secret
            return create_success_response(
                {
                    "invite": invite_public(invite, tenant_name=tenant.name),
                    "emailSent": bool(mail.get("sent")),
                    "emailReason": mail.get("reason"),
                }
            )

    @Get("/tenants/invites")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin")
    def list_invites(self, user=None, query: dict | None = None):
        require_user(user)
        tid = resolve_tenant_id(user)
        status_filter = ((query or {}).get("status") or "").strip().lower()
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            rows = list(
                session.exec(select(TenantInvite).where(TenantInvite.tenant_id == tid)).all()
            )
            rows.sort(key=lambda r: r.created_at or datetime.utcnow(), reverse=True)
            now = datetime.utcnow()
            out = []
            dirty = False
            for inv in rows:
                before = inv.status
                mark_expired_if_needed(inv, now)
                if inv.status != before:
                    session.add(inv)
                    dirty = True
                if status_filter and inv.status != status_filter:
                    continue
                out.append(invite_public(inv, tenant_name=tenant.name if tenant else None))
            if dirty:
                session.commit()
            return create_success_response({"invites": out})

    @Delete("/tenants/invites/{inviteId}")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin")
    def revoke_invite(self, inviteId: str, user=None):
        require_user(user)
        tid = resolve_tenant_id(user)
        with get_session() as session:
            invite = session.get(TenantInvite, int(inviteId))
            if not invite or int(invite.tenant_id) != int(tid):
                raise NotFoundError("Invite not found")
            if invite.status == "accepted":
                raise ConflictError("Accepted invites cannot be revoked")
            invite.status = "revoked"
            invite.updated_at = datetime.utcnow()
            session.add(invite)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="invite.revoke",
                resource_type="tenant_invite",
                resource_id=str(invite.invite_id),
                detail=json.dumps({"email": invite.email}),
            )
            session.commit()
            return create_success_response(
                {"invite": invite_public(invite), "revoked": True}
            )

    @Get("/tenants/invites/preview")
    @ApiPublic()
    def preview_invite(self, query: dict | None = None):
        token = ((query or {}).get("token") or "").strip()
        with get_session() as session:
            invite = load_invite_by_raw_token(session, token)
            tenant = session.get(Tenant, invite.tenant_id)
            session.commit()  # persist expired transition if any
            return create_success_response(
                {
                    "email": invite.email,
                    "role": invite.role,
                    "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
                    "tenantName": (tenant.app_display_name or tenant.name) if tenant else None,
                    "status": invite.status,
                }
            )

    @Post("/tenants/invites/accept")
    @ApiPublic()
    def accept_invite(self, data: dict, event: dict | None = None):
        """Accept invite.

        Authenticated: attach current user (email must match).
        Unauthenticated: provide username + password (+ matching email) to register into the tenant.
        """
        data = data or {}
        token = (data.get("token") or "").strip()
        auth_user = _optional_user(event)

        with get_session() as session:
            invite = load_invite_by_raw_token(session, token)
            tenant = session.get(Tenant, invite.tenant_id)
            if not tenant or not tenant.is_active:
                raise NotFoundError("Tenant not found")

            if auth_user and auth_user.get("userId"):
                user = session.get(User, int(auth_user["userId"]))
                if not user or not user.is_active:
                    raise AppError("Unauthenticated", 401, "UNAUTHORIZED")
                accept_invite_for_user(session, invite, user)
                write_audit(
                    session,
                    tenant_id=invite.tenant_id,
                    actor_user_id=user.user_id,
                    action="invite.accept",
                    resource_type="tenant_invite",
                    resource_id=str(invite.invite_id),
                )
                session.commit()
                session.refresh(user)
                tokens = _session_tokens_for_user(session, user)
                return create_success_response(
                    {
                        "accepted": True,
                        "tenantId": invite.tenant_id,
                        "role": invite.role,
                        **tokens,
                    }
                )

            # Register-then-accept
            username = (data.get("username") or "").strip()
            email = (data.get("email") or invite.email or "").strip().lower()
            password = data.get("password")
            if not username:
                raise ValidationError("username is required to accept without signing in")
            if password is None or not isinstance(password, str) or password == "":
                raise ValidationError("password is required to accept without signing in")
            if len(password) < 8:
                raise ValidationError("password must be at least 8 characters")
            assert_invite_email_matches(invite, email)

            if session.exec(select(User).where(User.email == email)).first():
                raise ConflictError(
                    "An account with this email already exists. Sign in, then accept the invite."
                )
            if session.exec(select(User).where(User.username == username)).first():
                raise ConflictError("This username is already taken. Please choose another.")

            # Bootstrap roles if needed
            try:
                from modules.platform.src.controllers.auth_controller import (
                    _ensure_platform_rbac,
                )

                _ensure_platform_rbac(session)
            except Exception:
                pass

            role = get_role_by_name(session, invite.role)
            user = User(
                username=username,
                email=email,
                password=bcrypt.hash(password),
                role_id=role.role_id,
                tenant_id=invite.tenant_id,
                is_active=True,
            )
            session.add(user)
            session.flush()
            accept_invite_for_user(session, invite, user)
            write_audit(
                session,
                tenant_id=invite.tenant_id,
                actor_user_id=user.user_id,
                action="invite.accept_register",
                resource_type="tenant_invite",
                resource_id=str(invite.invite_id),
            )
            session.commit()
            session.refresh(user)
            tokens = _session_tokens_for_user(session, user)
            return create_success_response(
                {
                    "accepted": True,
                    "registered": True,
                    "tenantId": invite.tenant_id,
                    "role": invite.role,
                    **tokens,
                }
            )
