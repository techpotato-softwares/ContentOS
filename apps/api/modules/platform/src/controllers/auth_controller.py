from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timedelta

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
    EmailOtpChallenge,
)
from utils.webtoken import generate_tokens
from utils import email_otp as otp_util
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


def _issue_auth_tokens(session, user: User) -> dict:
    """Same JWT + user payload as password login (tenant session via tenantId claim)."""
    role, permission_codes = _user_permissions(session, user.role_id)
    modules = _modules_for_tenant(session, user.tenant_id)
    payload = _token_payload(user, role, permission_codes, modules)
    tokens = generate_tokens(payload)
    return {
        "success": True,
        **tokens,
        "user": _auth_user_dict(user, role, permission_codes, modules),
    }


def _cleanup_otp_rows(session, *, email: str | None = None) -> None:
    """Purge OTP rows that are past the rate-limit retention window (or 7 days)."""
    now = datetime.utcnow()
    window = max(
        otp_util.otp_email_rate_limit()[1],
        otp_util.otp_ip_rate_limit()[1],
    )
    retain_after = now - timedelta(seconds=window)
    ancient = now - timedelta(days=7)
    q = select(EmailOtpChallenge)
    if email:
        q = q.where(EmailOtpChallenge.email == email)
    rows = session.exec(q).all()
    for row in rows:
        if row.created_at < ancient:
            session.delete(row)
            continue
        is_done = row.consumed_at is not None or row.expires_at < now
        if is_done and row.created_at < retain_after:
            session.delete(row)


def _count_recent_otp_requests(
    session, *, email: str | None = None, ip: str | None = None, window_seconds: int
) -> int:
    since = datetime.utcnow() - timedelta(seconds=window_seconds)
    q = select(EmailOtpChallenge).where(EmailOtpChallenge.created_at >= since)
    if email:
        q = q.where(EmailOtpChallenge.email == email)
    if ip:
        q = q.where(EmailOtpChallenge.request_ip == ip)
    return len(session.exec(q).all())


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
            if not user or not bcrypt.verify(password, user.password):
                raise AppError("Invalid username or password", 401, "UNAUTHORIZED")
            auth = _issue_auth_tokens(session, user)
            return create_success_response(
                {**auth, "message": "Login successful"}
            )

    @Post("/auth/otp/request")
    @ApiPublic()
    def request_otp(self, data: dict, event=None):
        """Send a short-lived email OTP for passwordless login (existing users only)."""
        body = data or {}
        email = otp_util.normalize_email(body.get("email"))
        if not otp_util.is_valid_email(email):
            raise ValidationError("A valid email address is required")

        headers = (event or {}).get("headers") or {}
        # API Gateway / proxies may lowercase header names
        request_ip = (
            headers.get("X-Forwarded-For")
            or headers.get("x-forwarded-for")
            or headers.get("X-Real-IP")
            or headers.get("x-real-ip")
            or ""
        )
        if isinstance(request_ip, str) and "," in request_ip:
            request_ip = request_ip.split(",")[0].strip()
        request_ip = (request_ip or None) and str(request_ip)[:64]

        with get_session() as session:
            user = session.exec(
                select(User).where(
                    (User.email == email) & (User.is_active == True)  # noqa: E712
                )
            ).first()
            if not user:
                raise AppError(
                    "No account found for this email. Register first or use password login.",
                    404,
                    "NOT_FOUND",
                )

            email_limit, email_window = otp_util.otp_email_rate_limit()
            if (
                _count_recent_otp_requests(
                    session, email=email, window_seconds=email_window
                )
                >= email_limit
            ):
                raise AppError(
                    "Too many code requests for this email. Please wait and try again.",
                    429,
                    "RATE_LIMITED",
                )

            if request_ip:
                ip_limit, ip_window = otp_util.otp_ip_rate_limit()
                if (
                    _count_recent_otp_requests(
                        session, ip=request_ip, window_seconds=ip_window
                    )
                    >= ip_limit
                ):
                    raise AppError(
                        "Too many code requests from this network. Please wait and try again.",
                        429,
                        "RATE_LIMITED",
                    )

            _cleanup_otp_rows(session, email=email)
            # Invalidate any still-active challenges for this email
            active = session.exec(
                select(EmailOtpChallenge).where(
                    (EmailOtpChallenge.email == email)
                    & (EmailOtpChallenge.consumed_at == None)  # noqa: E711
                    & (EmailOtpChallenge.expires_at > datetime.utcnow())
                )
            ).all()
            for row in active:
                row.consumed_at = datetime.utcnow()
                session.add(row)

            code = otp_util.generate_otp_code()
            challenge = EmailOtpChallenge(
                email=email,
                code_hash=otp_util.hash_otp(code, email=email),
                purpose="login",
                expires_at=otp_util.otp_expires_at(),
                attempts=0,
                max_attempts=otp_util.otp_max_attempts(),
                request_ip=request_ip,
            )
            session.add(challenge)
            session.commit()
            session.refresh(challenge)

            expires_minutes = max(1, otp_util.otp_ttl_seconds() // 60)
            send_result = otp_util.send_login_otp_email(
                to_email=email, code=code, expires_minutes=expires_minutes
            )
            # Drop plaintext reference immediately
            del code

            if not (isinstance(send_result, dict) and send_result.get("sent")):
                reason = (
                    (send_result or {}).get("reason")
                    if isinstance(send_result, dict)
                    else "unknown"
                )
                err = (
                    (send_result or {}).get("error")
                    if isinstance(send_result, dict)
                    else None
                )
                # Roll back challenge so user can retry after fixing email config
                session.delete(challenge)
                session.commit()
                detail = f" ({err})" if err else ""
                raise AppError(
                    f"Could not deliver sign-in email{detail}. "
                    "Check EMAIL_TRANSPORT / SMTP or SES settings.",
                    502,
                    "EMAIL_DELIVERY_FAILED",
                )

            payload = {
                "success": True,
                "message": "A sign-in code has been sent to your email.",
                "email": email,
                "expiresIn": otp_util.otp_ttl_seconds(),
                "otpId": challenge.otp_id,
            }
            # Local-only hint (Mailpit / file inbox) — never for real Gmail/SES
            if os.environ.get("IS_LOCAL") == "true" and isinstance(send_result, dict):
                inbox = send_result.get("inboxUrl")
                if inbox:
                    payload["inboxUrl"] = inbox
                    payload["message"] = (
                        "A sign-in code has been sent. Open the local mailbox to read it."
                    )
            return create_success_response(payload)

    @Post("/auth/otp/verify")
    @ApiPublic()
    def verify_otp(self, data: dict):
        """Verify email OTP and issue the same JWT + tenant session as password login."""
        body = data or {}
        email = otp_util.normalize_email(body.get("email"))
        code = str(body.get("code") or body.get("otp") or "").strip()
        if not otp_util.is_valid_email(email):
            raise ValidationError("A valid email address is required")
        if not code or not code.isdigit() or len(code) < 4 or len(code) > 8:
            raise ValidationError("Enter the numeric sign-in code from your email")

        with get_session() as session:
            user = session.exec(
                select(User).where(
                    (User.email == email) & (User.is_active == True)  # noqa: E712
                )
            ).first()
            if not user:
                raise AppError(
                    "No account found for this email.",
                    404,
                    "NOT_FOUND",
                )

            challenge = session.exec(
                select(EmailOtpChallenge)
                .where(
                    (EmailOtpChallenge.email == email)
                    & (EmailOtpChallenge.purpose == "login")
                    & (EmailOtpChallenge.consumed_at == None)  # noqa: E711
                )
                .order_by(EmailOtpChallenge.created_at.desc())  # type: ignore[arg-type]
            ).first()

            if not challenge:
                raise AppError(
                    "No active sign-in code. Request a new code and try again.",
                    400,
                    "OTP_NOT_FOUND",
                )

            if challenge.expires_at < datetime.utcnow():
                challenge.consumed_at = datetime.utcnow()
                session.add(challenge)
                session.commit()
                raise AppError(
                    "This sign-in code has expired. Request a new one.",
                    400,
                    "OTP_EXPIRED",
                )

            if challenge.attempts >= challenge.max_attempts:
                challenge.consumed_at = datetime.utcnow()
                session.add(challenge)
                session.commit()
                raise AppError(
                    "Too many incorrect attempts. Request a new sign-in code.",
                    429,
                    "OTP_ATTEMPTS_EXCEEDED",
                )

            if not otp_util.verify_otp_hash(
                code, email=email, code_hash=challenge.code_hash
            ):
                challenge.attempts += 1
                if challenge.attempts >= challenge.max_attempts:
                    challenge.consumed_at = datetime.utcnow()
                session.add(challenge)
                session.commit()
                remaining = max(0, challenge.max_attempts - challenge.attempts)
                if remaining == 0:
                    raise AppError(
                        "Too many incorrect attempts. Request a new sign-in code.",
                        429,
                        "OTP_ATTEMPTS_EXCEEDED",
                    )
                raise AppError(
                    f"Invalid sign-in code. {remaining} attempt(s) remaining.",
                    401,
                    "OTP_INVALID",
                )

            # Success: consume so the code cannot be reused
            challenge.consumed_at = datetime.utcnow()
            session.add(challenge)
            session.commit()

            auth = _issue_auth_tokens(session, user)
            _cleanup_otp_rows(session, email=email)
            session.commit()
            return create_success_response(
                {**auth, "message": "Login successful"}
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
