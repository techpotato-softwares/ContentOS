from __future__ import annotations

import json
import re
import secrets
from passlib.hash import bcrypt
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from decorators import Controller, Post, Get
from decorators.auth_decorators import ApiPublic, RequirePermission
from database import get_session
from database.models import (
    User,
    Role,
    RolePermission,
    Permission,
    Tenant,
    OAuthLoginState,
)
from utils.webtoken import generate_tokens
from middleware.error_handler import (
    AppError,
    ValidationError,
    ConflictError,
    create_success_response,
    CORS,
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


def _token_payload(user: User, role: Role | None, permissions: list[str], modules: list[str]) -> dict:
    """JWT claims: camelCase is the API convention; role + tenantId required for authz."""
    return {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": role.role_name if role else None,
        "tenantId": user.tenant_id,
        "permissions": permissions,
        "modulesEnabled": modules,
    }


def _unique_index_names_for_columns(table, column_names: set[str]) -> frozenset[str]:
    """Resolve unique index/constraint names from SQLAlchemy metadata (no hard-coded guesses)."""
    names: set[str] = set()
    cols = {table.c[n] for n in column_names if n in table.c}
    for idx in table.indexes:
        if idx.unique and idx.name and cols.intersection(idx.columns):
            names.add(idx.name)
    for cst in table.constraints:
        if isinstance(cst, UniqueConstraint) and cst.name:
            cst_cols = set(cst.columns)
            if cols.intersection(cst_cols):
                names.add(cst.name)
    return frozenset(names)


# Resolved from models: Field(unique=True) → ix_users_email / ix_users_username
_USER_IDENTITY_CONSTRAINTS = _unique_index_names_for_columns(
    User.__table__, {"email", "username"}
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
    }


def _issue_session(session, user: User) -> dict:
    role, permission_codes = _user_permissions(session, user.role_id)
    modules = _modules_for_tenant(session, user.tenant_id)
    payload = _token_payload(user, role, permission_codes, modules)
    tokens = generate_tokens(payload)
    return {
        "success": True,
        **tokens,
        "user": _auth_user_dict(user, role, permission_codes, modules),
    }


def _password_ok(user: User | None, password: str) -> bool:
    if not user or not user.password:
        return False
    try:
        return bool(bcrypt.verify(password, user.password))
    except Exception:
        return False


def _cleanup_oauth_states(session) -> None:
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    rows = session.exec(select(OAuthLoginState)).all()
    for row in rows:
        if row.consumed_at is not None or row.expires_at < now or row.created_at < cutoff:
            session.delete(row)


def _new_oauth_state(
    *, kind: str, user_id: int | None = None, ttl_seconds: int = 600
) -> OAuthLoginState:
    from datetime import datetime, timedelta

    return OAuthLoginState(
        state_id=secrets.token_urlsafe(32),
        provider="google",
        kind=kind,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
    )


def _google_frontend_error(code: str, message: str) -> dict:
    from urllib.parse import urlencode
    from utils.google_oauth_secrets import google_frontend_redirect

    qs = urlencode({"oauthError": code, "oauthMessage": message})
    loc = f"{google_frontend_redirect()}/login?{qs}"
    return {"statusCode": 302, "headers": {**CORS, "Location": loc}, "body": ""}


def _username_from_google(email: str, name: str | None) -> str:
    local = (email.split("@")[0] if email else "user").lower()
    local = re.sub(r"[^a-z0-9._-]+", "", local)[:24] or "user"
    return local


def _upsert_google_user(
    session, *, google_sub: str, email: str, name: str | None
) -> tuple[User, str]:
    """Return (user, outcome) where outcome is created|linked|login."""
    email = email.strip().lower()
    by_sub = session.exec(select(User).where(User.google_sub == google_sub)).first()
    if by_sub:
        return by_sub, "login"

    by_email = session.exec(select(User).where(User.email == email)).first()
    if by_email:
        if by_email.google_sub and by_email.google_sub != google_sub:
            raise ConflictError(
                "This email is already linked to a different Google account. "
                "Sign in with password or the original Google account."
            )
        by_email.google_sub = google_sub
        if by_email.auth_provider == "password":
            by_email.auth_provider = "password+google"
        else:
            by_email.auth_provider = "google"
        session.add(by_email)
        session.flush()
        return by_email, "linked"

    role = _ensure_platform_rbac(session)
    display = (name or email.split("@")[0] or "My Company").strip()
    company_name = f"{display}'s workspace" if display else "My workspace"
    slug = _unique_tenant_slug(session, company_name)
    training = TenantTrainingSchema(
        company=CompanySection(legal_name=company_name, display_name=company_name),
        brand_visual=BrandVisualSection(ui_mode="platform"),
    )
    tenant = Tenant(
        name=company_name,
        slug=slug,
        modules_enabled=json.dumps(["platform", "tenants", "agent", "publishing"]),
        training_json=training.model_dump_json(),
        ui_mode="platform",
        app_display_name=company_name,
    )
    session.add(tenant)
    session.flush()

    base_username = _username_from_google(email, name)
    username = base_username
    n = 0
    while session.exec(select(User).where(User.username == username)).first():
        n += 1
        username = f"{base_username[:20]}{n}"

    user = User(
        username=username,
        email=email,
        password=None,
        auth_provider="google",
        google_sub=google_sub,
        role_id=role.role_id,
        tenant_id=tenant.tenant_id,
    )
    session.add(user)
    session.flush()
    return user, "created"


@Controller(path="/api", lambda_name="auth")
class AuthController:
    @Post("/login")
    @ApiPublic()
    def login(self, data: dict):
        username = (data or {}).get("username")
        password = (data or {}).get("password")
        if not username or not password:
            raise ValidationError("Username and password are required")
        with get_session() as session:
            user = session.exec(
                select(User).where(
                    ((User.username == username) | (User.email == username))
                    & (User.is_active == True)
                )
            ).first()
            if not _password_ok(user, password):
                raise AppError("Invalid username or password", 401, "UNAUTHORIZED")
            auth = _issue_session(session, user)
            return create_success_response({**auth, "message": "Login successful"})

    @Get("/auth/google/start")
    @ApiPublic()
    def google_start(self, query: dict | None = None):
        """Begin Google OAuth — 302 to Google authorize URL with CSRF state."""
        from utils.google_oauth import build_google_authorize_url
        from utils.google_oauth_secrets import get_google_oauth_secrets

        secrets_cfg = get_google_oauth_secrets()
        if not secrets_cfg.client_id or not secrets_cfg.client_secret:
            raise AppError(
                "Google sign-in is not configured. Set GOOGLE_CLIENT_ID/SECRET "
                "(local) or update Secrets Manager /{app}/{env}/google-oauth.",
                503,
                "GOOGLE_OAUTH_NOT_CONFIGURED",
            )

        with get_session() as session:
            _cleanup_oauth_states(session)
            state = _new_oauth_state(kind="csrf", ttl_seconds=600)
            session.add(state)
            session.commit()
            try:
                url = build_google_authorize_url(state=state.state_id)
            except ValueError as e:
                raise AppError(str(e), 503, "GOOGLE_OAUTH_NOT_CONFIGURED") from e
            return {
                "statusCode": 302,
                "headers": {**CORS, "Location": url},
                "body": "",
            }

    @Get("/auth/google/callback")
    @ApiPublic()
    def google_callback(self, query: dict | None = None):
        """Google redirects here. Validate state, upsert user, redirect with one-time code."""
        from datetime import datetime
        from urllib.parse import urlencode
        from utils.google_oauth import exchange_google_code, fetch_google_userinfo
        from utils.google_oauth_secrets import google_frontend_redirect

        qs = query or {}
        if qs.get("error"):
            return _google_frontend_error(
                "GOOGLE_DENIED",
                str(qs.get("error_description") or qs.get("error") or "Google sign-in was cancelled"),
            )

        code = (qs.get("code") or "").strip()
        state_id = (qs.get("state") or "").strip()
        if not code or not state_id:
            return _google_frontend_error("OAUTH_INVALID", "Missing OAuth code or state")

        with get_session() as session:
            state = session.get(OAuthLoginState, state_id)
            if (
                not state
                or state.provider != "google"
                or state.kind != "csrf"
                or state.consumed_at is not None
                or state.expires_at < datetime.utcnow()
            ):
                return _google_frontend_error(
                    "OAUTH_STATE",
                    "Invalid or expired sign-in state. Please try Google again.",
                )

            state.consumed_at = datetime.utcnow()
            session.add(state)
            session.commit()

            try:
                token_payload = exchange_google_code(code)
                access = token_payload.get("access_token")
                if not access:
                    return _google_frontend_error(
                        "GOOGLE_TOKEN", "Google did not return an access token"
                    )
                info = fetch_google_userinfo(access)
            except ConflictError as e:
                return _google_frontend_error("OAUTH_CONFLICT", e.message)
            except Exception:
                return _google_frontend_error(
                    "GOOGLE_TOKEN",
                    "Could not verify your Google account. Please try again.",
                )

            google_sub = str(info.get("sub") or "").strip()
            email = str(info.get("email") or "").strip().lower()
            email_verified = bool(info.get("email_verified"))
            name = (info.get("name") or info.get("given_name") or "").strip() or None
            if not google_sub or not email:
                return _google_frontend_error(
                    "GOOGLE_PROFILE", "Google did not provide email identity"
                )
            if not email_verified:
                return _google_frontend_error(
                    "EMAIL_UNVERIFIED",
                    "Your Google email must be verified to continue.",
                )

            try:
                user, outcome = _upsert_google_user(
                    session, google_sub=google_sub, email=email, name=name
                )
                session.commit()
                session.refresh(user)
            except ConflictError as e:
                session.rollback()
                return _google_frontend_error("OAUTH_CONFLICT", e.message)
            except Exception:
                session.rollback()
                return _google_frontend_error(
                    "OAUTH_PROVISION",
                    "Could not create your workspace. Please try again.",
                )

            exchange = _new_oauth_state(
                kind="exchange", user_id=user.user_id, ttl_seconds=120
            )
            session.add(exchange)
            session.commit()

            qs_out = urlencode(
                {
                    "code": exchange.state_id,
                    "oauth": outcome,
                }
            )
            loc = f"{google_frontend_redirect()}/login/oauth/callback?{qs_out}"
            return {"statusCode": 302, "headers": {**CORS, "Location": loc}, "body": ""}

    @Post("/auth/google/exchange")
    @ApiPublic()
    def google_exchange(self, data: dict):
        """Exchange one-time OAuth code for the same JWT + tenant session as password login."""
        from datetime import datetime

        code = ((data or {}).get("code") or "").strip()
        if not code:
            raise ValidationError("code is required")

        with get_session() as session:
            row = session.get(OAuthLoginState, code)
            if (
                not row
                or row.provider != "google"
                or row.kind != "exchange"
                or row.consumed_at is not None
                or row.expires_at < datetime.utcnow()
                or not row.user_id
            ):
                raise AppError(
                    "Invalid or expired Google sign-in code. Please try again.",
                    400,
                    "OAUTH_EXCHANGE_INVALID",
                )
            user = session.get(User, row.user_id)
            if not user or not user.is_active:
                raise AppError("User account is not available", 401, "UNAUTHORIZED")

            row.consumed_at = datetime.utcnow()
            session.add(row)
            session.commit()

            auth = _issue_session(session, user)
            return create_success_response(
                {**auth, "message": "Google sign-in successful"}
            )

    @Post("/auth/refresh")
    @ApiPublic()
    def refresh(self, data: dict):
        from utils.webtoken import verify_refresh_token

        token = (data or {}).get("refreshToken")
        if not token:
            raise ValidationError("Refresh token is required")
        decoded = verify_refresh_token(token)
        clean = {
            k: decoded[k]
            for k in (
                "userId",
                "username",
                "email",
                "role",
                "tenantId",
                "permissions",
                "modulesEnabled",
            )
            if k in decoded
        }
        tokens = generate_tokens(clean)
        return create_success_response(
            {"success": True, "message": "Token refreshed successfully", **tokens}
        )

    @Post("/register")
    @ApiPublic()
    def register(self, data: dict):
        """Self-serve signup: Tenant + User + tenant_admin membership in one transaction.

        Production must not require scripts/seed.py. Roles/permissions are ensured
        idempotently here. On any failure the whole unit rolls back (no orphans).
        """
        body = data or {}
        username = (body.get("username") or "").strip()
        email = (body.get("email") or "").strip().lower()
        password = body.get("password")
        company_name = (
            body.get("companyName") or body.get("company_name") or ""
        ).strip()
        if not username:
            raise ValidationError("username is required")
        if not email:
            raise ValidationError("email is required")
        if password is None or not isinstance(password, str) or password == "":
            raise ValidationError("password is required")
        if len(password) < 8:
            raise ValidationError("password must be at least 8 characters")
        if not company_name:
            raise ValidationError("companyName is required")

        preferred_slug = body.get("slug")
        if preferred_slug is not None:
            preferred_slug = str(preferred_slug).strip() or None

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
                    auth_provider="password",
                    role_id=role.role_id,
                    tenant_id=tenant.tenant_id,
                )
                session.add(user)
                session.flush()

                # Single atomic commit: Tenant + User (tenant_admin membership via role_id)
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
                        "message": "Registered",
                        **tokens,
                        "user": _auth_user_dict(
                            user, role, permission_codes, modules
                        ),
                        "tenant": {
                            "tenantId": tenant.tenant_id,
                            "name": tenant.name,
                            "slug": tenant.slug,
                        },
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

    @Get("/me")
    @RequirePermission("agent:chat", "tenant:admin", "admin:tenants", "admin")
    def me(self, user=None):
        return create_success_response({"user": user})
