from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, cast

import passlib.hash as _passlib_hash
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

# passlib exposes bcrypt dynamically; getattr keeps runtime + type-checkers happy
bcrypt = cast(Any, getattr(_passlib_hash, "bcrypt"))

from decorators import Controller, Post, Get
from decorators.auth_decorators import ApiPublic, RequirePermission
from database import get_session
from database.models import User, Role, RolePermission, Permission, Tenant
from utils.webtoken import JWTPayload, generate_tokens
from utils.auth_tokens import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    consume_token,
    ensure_auth_schema,
    is_local,
    issue_token,
)
from utils.auth_email import send_password_reset_email, send_verification_email
from middleware.error_handler import (
    AppError,
    ValidationError,
    ConflictError,
    create_success_response,
)
from training.schema import TenantTrainingSchema, CompanySection, BrandVisualSection

# Platform RBAC catalog — ensured idempotently on register so production signup
# does not depend on scripts/seed.py (seed is local/dev only).
_PERMS = [
    ("admin:tenants", "Manage all tenants"),
    ("training:manage", "Edit training schema"),
    ("tenant:admin", "Tenant administration"),
    ("agent:chat", "Agent chat & generate"),
    ("posts:review", "Review posts"),
    ("posts:publish", "Publish to LinkedIn"),
    ("admin", "Legacy admin"),
]

_ROLES = {
    "super_admin": [p[0] for p in _PERMS],
    "tenant_admin": [
        "training:manage",
        "tenant:admin",
        "agent:chat",
        "posts:review",
        "posts:publish",
    ],
    "tenant_member": ["agent:chat", "posts:review", "posts:publish"],
}

# Generic copy for request endpoints — prevents email/account enumeration
_VERIFY_REQUEST_MSG = (
    "If an account exists for that email, we sent a verification link."
)
_RESET_REQUEST_MSG = (
    "If an account exists for that email, we sent a password reset link."
)

# Platform RBAC catalog — ensured idempotently on register so production signup
# does not depend on scripts/seed.py (seed is local/dev only).
_PERMS = [
    ("admin:tenants", "Manage all tenants"),
    ("training:manage", "Edit training schema"),
    ("tenant:admin", "Tenant administration"),
    ("agent:chat", "Agent chat & generate"),
    ("posts:review", "Review posts"),
    ("posts:publish", "Publish to LinkedIn"),
    ("admin", "Legacy admin"),
]

_ROLES = {
    "super_admin": [p[0] for p in _PERMS],
    "tenant_admin": [
        "training:manage",
        "tenant:admin",
        "agent:chat",
        "posts:review",
        "posts:publish",
    ],
    "tenant_member": ["agent:chat", "posts:review", "posts:publish"],
}


def _user_permissions(session, role_id: int | None) -> tuple[Role | None, list[str]]:
    role = session.get(Role, role_id) if role_id else None
    permission_codes: list[str] = []
    if role:
        rps = session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.role_id, RolePermission.is_active == True
            )
        ).all()
        for rp in rps:
            perm = session.get(Permission, rp.permission_id)
            if perm and perm.is_active:
                permission_codes.append(perm.permission_code)
    return role, permission_codes


def _modules_for_tenant(session, tenant_id: int | None) -> list[str]:
    modules = ["platform", "tenants", "agent", "publishing"]
    if tenant_id:
        tenant = session.get(Tenant, tenant_id)
        if tenant and tenant.modules_enabled:
            try:
                modules = json.loads(tenant.modules_enabled)
            except Exception:
                pass
    return modules


def _email_verified(user: User) -> bool:
    return bool(getattr(user, "email_verified_at", None))


def _token_payload(
    user: User, role: Role | None, permissions: list[str], modules: list[str]
) -> JWTPayload:
    """JWT claims: camelCase is the API convention; role + tenantId required for authz."""
    payload: JWTPayload = {
        "userId": user.user_id or 0,
        "username": user.username or "",
        "email": user.email or "",
        "tenantId": user.tenant_id if user.tenant_id is not None else 0,
        "permissions": permissions,
        "modulesEnabled": modules,
        "emailVerified": _email_verified(user),
        "tv": int(getattr(user, "token_version", 0) or 0),
    }
    if role and role.role_name:
        payload["role"] = role.role_name
    return payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _unique_index_names_for_columns(table: Any, column_names: set[str]) -> frozenset[str]:
    """Resolve unique index/constraint names from SQLAlchemy metadata (no hard-coded guesses)."""
    names: set[str] = set()
    cols = {table.c[n] for n in column_names if n in table.c}
    for idx in table.indexes:
        if idx.unique and idx.name and cols.intersection(idx.columns):
            names.add(str(idx.name))
    for cst in table.constraints:
        if isinstance(cst, UniqueConstraint) and cst.name:
            cst_cols = set(cst.columns)
            if cols.intersection(cst_cols):
                names.add(str(cst.name))
    return frozenset(names)


# Resolved from models: Field(unique=True) → ix_users_email / ix_users_username
_USER_IDENTITY_CONSTRAINTS = _unique_index_names_for_columns(
    cast(Any, User).__table__, {"email", "username"}
)


def _integrity_constraint_name(exc: IntegrityError) -> str | None:
    """Best-effort PostgreSQL constraint/index name from IntegrityError."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    diag = getattr(orig, "diag", None)
    if diag is not None:
        name = getattr(diag, "constraint_name", None)
        if name:
            return str(name)
    # Some drivers expose constraint on the exception itself
    name = getattr(orig, "constraint_name", None)
    return str(name) if name else None


def _is_user_identity_unique_violation(exc: IntegrityError) -> bool:
    """True only for users.email / users.username uniqueness — not slug/RBAC/other."""
    constraint = _integrity_constraint_name(exc)
    if constraint and constraint in _USER_IDENTITY_CONSTRAINTS:
        return True

    # SQLite (and some drivers): "UNIQUE constraint failed: users.email"
    msg = str(getattr(exc, "orig", None) or exc).lower()
    if "users.email" in msg or "users.username" in msg:
        return True

    # PostgreSQL unique_violation without a matching constraint name → not a user conflict
    # (e.g. tenants.slug, roles.role_name, permissions.permission_code, unknown)
    return False


def _user_conflict_from_integrity(exc: IntegrityError) -> ConflictError | None:
    if _is_user_identity_unique_violation(exc):
        return ConflictError(
            "An account with this email or username already exists."
        )
    return None


def _slugify(company_name: str) -> str:
    raw = (company_name or "").lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", raw)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:48]
    return slug or "company"


def _unique_tenant_slug(session, company_name: str, preferred: str | None = None) -> str:
    base = _slugify(preferred or company_name)
    candidate = base
    n = 0
    while session.exec(select(Tenant).where(Tenant.slug == candidate)).first():
        n += 1
        if n < 100:
            suffix = f"-{n}"
        else:
            suffix = f"-{secrets.token_hex(3)}"
        candidate = f"{base[: max(1, 48 - len(suffix))]}{suffix}"
    return candidate


def _ensure_platform_rbac(session) -> Role:
    """Idempotently create permissions + roles; return tenant_admin for membership.

    Concurrent signup uses SAVEPOINTs so unique races on roles/permissions do not
    abort the outer registration transaction.
    """
    perm_map: dict[str, int] = {}
    for code, name in _PERMS:
        existing = session.exec(
            select(Permission).where(Permission.permission_code == code)
        ).first()
        if not existing:
            try:
                with session.begin_nested():
                    existing = Permission(
                        permission_code=code, permission_name=name, description=name
                    )
                    session.add(existing)
                    session.flush()
            except IntegrityError:
                existing = session.exec(
                    select(Permission).where(Permission.permission_code == code)
                ).first()
                if not existing:
                    raise
        perm_map[code] = existing.permission_id  # type: ignore[assignment]

    tenant_admin: Role | None = None
    for role_name, codes in _ROLES.items():
        role = session.exec(select(Role).where(Role.role_name == role_name)).first()
        if not role:
            try:
                with session.begin_nested():
                    role = Role(role_name=role_name, description=role_name)
                    session.add(role)
                    session.flush()
            except IntegrityError:
                role = session.exec(
                    select(Role).where(Role.role_name == role_name)
                ).first()
                if not role:
                    raise
        for code in codes:
            pid = perm_map[code]
            rp = session.exec(
                select(RolePermission).where(
                    RolePermission.role_id == role.role_id,
                    RolePermission.permission_id == pid,
                )
            ).first()
            if not rp:
                try:
                    with session.begin_nested():
                        session.add(
                            RolePermission(role_id=role.role_id, permission_id=pid)
                        )
                        session.flush()
                except IntegrityError:
                    # Concurrent insert of the same link — safe to ignore
                    pass
        if role_name == "tenant_admin":
            tenant_admin = role

    if not tenant_admin:
        raise AppError("Unable to resolve tenant_admin role", 500, "SETUP")
    return tenant_admin


def _auth_user_dict(
    user: User, role: Role | None, permission_codes: list[str], modules: list[str]
) -> dict:
    return {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "roleName": role.role_name if role else None,
        "tenantId": user.tenant_id,
        "permissions": permission_codes,
        "modulesEnabled": modules,
        "emailVerified": _email_verified(user),
    }


def _maybe_dev_link(mail_result: dict) -> dict:
    if is_local() and mail_result.get("devLink"):
        return {"devLink": mail_result["devLink"]}
    return {}


@Controller(path="/api", lambda_name="auth")
class AuthController:
    @Post("/login")
    @ApiPublic()
    def login(self, data: dict, event=None):
        username = (data or {}).get("username")
        password = (data or {}).get("password")
        if not username or not password:
            raise ValidationError("Username and password are required")
        enforce_auth_rate_limit("login", identity=str(username), event=event)
        reject_seed_login_in_production(str(username), str(password))
        with get_session() as session:
            ensure_auth_schema(session)
            user = session.exec(
                select(User).where(
                    ((User.username == username) | (User.email == username))
                    & (User.is_active == True)
                )
            ).first()
            if not user or not bcrypt.verify(password, user.password):
                raise AppError("Invalid username or password", 401, "UNAUTHORIZED")
            role, permission_codes = _user_permissions(session, user.role_id)
            modules = _modules_for_tenant(session, user.tenant_id)
            payload = _token_payload(user, role, permission_codes, modules)
            tokens = generate_tokens(payload)
            return create_success_response(
                {
                    "success": True,
                    "message": "Login successful",
                    **tokens,
                    "user": _auth_user_dict(user, role, permission_codes, modules),
                }
            )

    @Post("/auth/refresh")
    @ApiPublic()
    def refresh(self, data: dict):
        from utils.webtoken import verify_refresh_token

        token = (data or {}).get("refreshToken")
        if not token:
            raise ValidationError("Refresh token is required")
        decoded = verify_refresh_token(token)
        with get_session() as session:
            ensure_auth_schema(session)
            user_id = decoded.get("userId")
            user = session.get(User, user_id) if user_id is not None else None
            if not user or not user.is_active:
                raise AppError("Invalid or expired refresh token", 401, "UNAUTHORIZED")
            expected_tv = int(getattr(user, "token_version", 0) or 0)
            if (decoded.get("tv") or 0) != expected_tv:
                raise AppError(
                    "Session expired — please sign in again",
                    401,
                    "SESSION_REVOKED",
                )
            role, permission_codes = _user_permissions(session, user.role_id)
            modules = _modules_for_tenant(session, user.tenant_id)
            payload = _token_payload(user, role, permission_codes, modules)
            tokens = generate_tokens(payload)
            return create_success_response(
                {
                    "success": True,
                    "message": "Token refreshed successfully",
                    **tokens,
                    "user": _auth_user_dict(user, role, permission_codes, modules),
                }
            )

    @Post("/register")
    @ApiPublic()
    def register(self, data: dict, event=None):
        """Create a company tenant + tenant_admin user."""
        username = (data or {}).get("username")
        email = (data or {}).get("email")
        password = (data or {}).get("password")
        company_name = (data or {}).get("companyName") or (data or {}).get("company_name")
        if not all([username, email, password, company_name]):
            raise ValidationError("username, email, password, companyName are required")
        enforce_auth_rate_limit("register", identity=str(email or username), event=event)
        reject_seed_login_in_production(str(username), str(password))
        reject_seed_login_in_production(str(email), str(password))
        slug = (
            (data or {}).get("slug")
            or company_name.lower().replace(" ", "-").replace("_", "-")[:48]
        )
        with get_session() as session:
            try:
                # Pre-checks for clear 409 messages (race still handled via IntegrityError)
                if session.exec(select(User).where(User.email == email)).first():
                    raise ConflictError(
                        "An account with this email already exists. Sign in or use a different email."
                    )
                if session.exec(select(User).where(User.username == username)).first():
                    raise ConflictError(
                        "This username is already taken. Please choose another."
                    )

                _ensure_platform_rbac(session)

                if invite_token:
                    from utils.tenant_invites import (
                        accept_invite_for_user,
                        get_role_by_name,
                        load_invite_by_raw_token,
                    )

                    invite = load_invite_by_raw_token(session, invite_token)
                    tenant = session.get(Tenant, invite.tenant_id)
                    if not tenant or not tenant.is_active:
                        raise ValidationError("Invite tenant is not available")
                    role = get_role_by_name(session, invite.role)
                    user = User(
                        username=username,
                        email=email,
                        password=bcrypt.hash(password),
                        role_id=role.role_id,
                        tenant_id=tenant.tenant_id,
                    )
                    session.add(user)
                    session.flush()
                    accept_invite_for_user(session, invite, user)
                    session.commit()
                    session.refresh(tenant)
                    session.refresh(user)
                    role, permission_codes = _user_permissions(session, user.role_id)
                    modules = _modules_for_tenant(session, user.tenant_id)
                    payload = _token_payload(user, role, permission_codes, modules)
                    tokens = generate_tokens(payload)
                    return create_success_response(
                        {
                            "success": True,
                            "message": "Registered via invite",
                            **tokens,
                            "user": _auth_user_dict(
                                user, role, permission_codes, modules
                            ),
                            "tenant": {
                                "tenantId": tenant.tenant_id,
                                "name": tenant.name,
                                "slug": tenant.slug,
                            },
                            "inviteAccepted": True,
                        }
                    )

                role = session.exec(
                    select(Role).where(Role.role_name == "tenant_admin")
                ).first()
                if not role:
                    role = _ensure_platform_rbac(session)
                slug = _unique_tenant_slug(session, company_name, preferred_slug)

                training = TenantTrainingSchema(
                    company=CompanySection(
                        legal_name=company_name, display_name=company_name
                    ),
                    brand_visual=BrandVisualSection(ui_mode="platform"),
                )
                tenant = Tenant(
                    name=company_name,
                    slug=slug,
                    modules_enabled=json.dumps(
                        ["platform", "tenants", "agent", "publishing"]
                    ),
                    training_json=training.model_dump_json(),
                    ui_mode="platform",
                    app_display_name=company_name,
                )
                session.add(tenant)
                session.flush()  # allocate tenant_id without committing

                user = User(
                    username=username,
                    email=email,
                    password=bcrypt.hash(password),
                    role_id=role.role_id,
                    tenant_id=tenant.tenant_id,
                )
                session.add(user)
                session.flush()

                raw_verify = issue_token(
                    session, user=user, purpose=PURPOSE_EMAIL_VERIFY
                )
                mail = send_verification_email(to_email=email, raw_token=raw_verify)

                # Single atomic commit: Tenant + User + verify token
                session.commit()
                session.refresh(tenant)
                session.refresh(user)

                role, permission_codes = _user_permissions(session, user.role_id)
                modules = _modules_for_tenant(session, user.tenant_id)
                payload = _token_payload(user, role, permission_codes, modules)
                if not payload.get("tenantId") or not payload.get("role"):
                    raise AppError(
                        "Registration incomplete: missing tenant or role in session",
                        500,
                        "SETUP",
                    )
                tokens = generate_tokens(payload)
                return create_success_response(
                    {
                        "success": True,
                        "message": "Registered — check your email to verify your account",
                        **tokens,
                        "user": _auth_user_dict(
                            user, role, permission_codes, modules
                        ),
                        "tenant": {
                            "tenantId": tenant.tenant_id,
                            "name": tenant.name,
                            "slug": tenant.slug,
                        },
                        "emailVerificationRequired": True,
                        **_maybe_dev_link(mail),
                    },
                    201,
                )
            except (ConflictError, ValidationError, AppError):
                session.rollback()
                raise
            except IntegrityError as e:
                session.rollback()
                # Only map users.email / users.username unique violations to 409.
                # Slug/RBAC/unknown integrity errors must not look like "email taken".
                conflict = _user_conflict_from_integrity(e)
                if conflict is not None:
                    raise conflict
                raise
            except Exception:
                session.rollback()
                raise

    @Post("/auth/verify-email/request")
    @ApiPublic()
    def verify_email_request(self, data: dict):
        email = ((data or {}).get("email") or "").strip().lower()
        if not email:
            raise ValidationError("email is required")
        out: dict = {"success": True, "message": _VERIFY_REQUEST_MSG}
        with get_session() as session:
            ensure_auth_schema(session)
            user = session.exec(
                select(User).where(User.email == email, User.is_active == True)
            ).first()
            if user and not _email_verified(user):
                try:
                    raw = issue_token(
                        session, user=user, purpose=PURPOSE_EMAIL_VERIFY
                    )
                    mail = send_verification_email(to_email=user.email, raw_token=raw)
                    session.commit()
                    out.update(_maybe_dev_link(mail))
                except AppError as e:
                    if e.code == "RATE_LIMITED":
                        raise
                    session.rollback()
                except Exception:
                    session.rollback()
            # Always same message (enumeration-safe)
        return create_success_response(out)

    @Post("/auth/verify-email/confirm")
    @ApiPublic()
    def verify_email_confirm(self, data: dict):
        raw = (data or {}).get("token") or ""
        with get_session() as session:
            ensure_auth_schema(session)
            _row, user = consume_token(
                session, raw_token=str(raw), purpose=PURPOSE_EMAIL_VERIFY
            )
            if not _email_verified(user):
                user.email_verified_at = _utc_now()
                user.updated_at = _utc_now()
                session.add(user)
            session.commit()
            session.refresh(user)
            role, permission_codes = _user_permissions(session, user.role_id)
            modules = _modules_for_tenant(session, user.tenant_id)
            payload = _token_payload(user, role, permission_codes, modules)
            tokens = generate_tokens(payload)
            return create_success_response(
                {
                    "success": True,
                    "message": "Email verified",
                    **tokens,
                    "user": _auth_user_dict(user, role, permission_codes, modules),
                }
            )

    @Post("/auth/password-reset/request")
    @ApiPublic()
    def password_reset_request(self, data: dict):
        email = ((data or {}).get("email") or "").strip().lower()
        if not email:
            raise ValidationError("email is required")
        out: dict = {"success": True, "message": _RESET_REQUEST_MSG}
        with get_session() as session:
            ensure_auth_schema(session)
            user = session.exec(
                select(User).where(User.email == email, User.is_active == True)
            ).first()
            if user:
                try:
                    raw = issue_token(
                        session, user=user, purpose=PURPOSE_PASSWORD_RESET
                    )
                    mail = send_password_reset_email(
                        to_email=user.email, raw_token=raw
                    )
                    session.commit()
                    out.update(_maybe_dev_link(mail))
                except AppError as e:
                    if e.code == "RATE_LIMITED":
                        raise
                    session.rollback()
                except Exception:
                    session.rollback()
        return create_success_response(out)

    @Post("/auth/password-reset/confirm")
    @ApiPublic()
    def password_reset_confirm(self, data: dict):
        raw = (data or {}).get("token") or ""
        password = (data or {}).get("password") or ""
        if not password or len(str(password)) < 8:
            raise ValidationError("password must be at least 8 characters")
        with get_session() as session:
            ensure_auth_schema(session)
            _row, user = consume_token(
                session, raw_token=str(raw), purpose=PURPOSE_PASSWORD_RESET
            )
            user.password = bcrypt.hash(password)
            user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
            user.updated_at = _utc_now()
            # Optional: mark email verified on successful reset via known mailbox
            if user.email_verified_at is None:
                user.email_verified_at = _utc_now()
            session.add(user)
            session.commit()
            return create_success_response(
                {
                    "success": True,
                    "message": "Password updated — sign in with your new password",
                }
            )

    @Get("/me")
    @RequirePermission("agent:chat", "tenant:admin", "admin:tenants", "admin")
    def me(self, user=None):
        with get_session() as session:
            ensure_auth_schema(session)
            row = session.get(User, int((user or {}).get("userId") or 0))
            if not row:
                return create_success_response({"user": user})
            role, permission_codes = _user_permissions(session, row.role_id)
            modules = _modules_for_tenant(session, row.tenant_id)
            return create_success_response(
                {
                    "user": {
                        **_auth_user_dict(row, role, permission_codes, modules),
                        # Keep JWT-shaped fields for clients reading /me.user
                        "role": role.role_name if role else None,
                        "tenantId": row.tenant_id,
                    }
                }
            )
