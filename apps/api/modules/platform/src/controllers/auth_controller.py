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
        ensure_onboarding_schema(session)
        tenant = session.get(Tenant, tenant_id)
        if tenant and tenant.modules_enabled:
            try:
                modules = json.loads(tenant.modules_enabled)
            except (json.JSONDecodeError, TypeError):
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
    # PostgreSQL unique_violation without a matching constraint name → not a user conflict
    # (e.g. tenants.slug, roles.role_name, permissions.permission_code, unknown)
    return "users.email" in msg or "users.username" in msg


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
    def login(self, data: dict, event=None):
        username = (data or {}).get("username")
        password = (data or {}).get("password")
        if not username or not password:
            raise ValidationError("Username and password are required")
        enforce_auth_rate_limit("login", identity=str(username), event=event)
        reject_seed_login_in_production(str(username), str(password))
        with get_session() as session:
            ensure_auth_schema(session)
            ensure_onboarding_schema(session)
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
        with get_session() as session:
            ensure_auth_schema(session)
            ensure_onboarding_schema(session)
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
        body = data or {}
        username = body.get("username")
        email = body.get("email")
        password = body.get("password")
        company_name = body.get("companyName") or body.get("company_name")
        invite_token = body.get("inviteToken") or body.get("invite_token")
        preferred_slug = body.get("slug")
        if not username or not email or not password:
            raise ValidationError("username, email, password are required")
        if not invite_token and not company_name:
            raise ValidationError("username, email, password, companyName are required")
        enforce_auth_rate_limit("register", identity=str(email or username), event=event)
        reject_seed_login_in_production(str(username), str(password))
        reject_seed_login_in_production(str(email), str(password))
        with get_session() as session:
            try:
                ensure_onboarding_schema(session)
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

                    invite = load_invite_by_raw_token(session, str(invite_token))
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

                # company_name required for self-serve tenant creation (checked above)
                assert company_name is not None
                role = session.exec(
                    select(Role).where(Role.role_name == "tenant_admin")
                ).first()
                if not role:
                    role = _ensure_platform_rbac(session)
                slug = _unique_tenant_slug(
                    session,
                    str(company_name),
                    str(preferred_slug) if preferred_slug else None,
                )

                training = TenantTrainingSchema(
                    company=CompanySection(
                        legal_name=str(company_name),
                        display_name=str(company_name),
                    ),
                    brand_visual=BrandVisualSection(ui_mode="platform"),
                )
                tenant = Tenant(
                    name=str(company_name),
                    slug=slug,
                    modules_enabled=json.dumps(
                        ["platform", "tenants", "agent", "publishing"]
                    ),
                    training_json=training.model_dump_json(),
                    ui_mode="platform",
                    app_display_name=str(company_name),
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
                mail = send_verification_email(to_email=str(email), raw_token=raw_verify)

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
                except Exception:  # noqa: BLE001 — enumeration-safe; never leak mail failures
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
                except Exception:  # noqa: BLE001 — enumeration-safe; never leak mail failures
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
            ensure_onboarding_schema(session)
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
