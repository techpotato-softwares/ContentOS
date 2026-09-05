from __future__ import annotations

import json
from datetime import datetime

from passlib.hash import bcrypt
from sqlmodel import select

from decorators import Controller, Post, Get
from decorators.auth_decorators import ApiPublic, RequirePermission
from database import get_session
from database.models import User, Role, RolePermission, Permission, Tenant
from utils.webtoken import generate_tokens
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
    create_success_response,
)
from training.schema import TenantTrainingSchema, CompanySection, BrandVisualSection

# Generic copy for request endpoints — prevents email/account enumeration
_VERIFY_REQUEST_MSG = (
    "If an account exists for that email, we sent a verification link."
)
_RESET_REQUEST_MSG = (
    "If an account exists for that email, we sent a password reset link."
)


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


def _token_payload(user: User, role: Role | None, permissions: list[str], modules: list[str]) -> dict:
    return {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": role.role_name if role else None,
        "tenantId": user.tenant_id,
        "permissions": permissions,
        "modulesEnabled": modules,
        "emailVerified": _email_verified(user),
        "tv": int(getattr(user, "token_version", 0) or 0),
    }


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
    def login(self, data: dict):
        username = (data or {}).get("username")
        password = (data or {}).get("password")
        if not username or not password:
            raise ValidationError("Username and password are required")
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
            user = session.get(User, int(user_id)) if user_id else None
            if not user or not user.is_active:
                raise AppError("Invalid or expired refresh token", 401, "UNAUTHORIZED")
            expected_tv = int(getattr(user, "token_version", 0) or 0)
            if int(decoded.get("tv") or 0) != expected_tv:
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
    def register(self, data: dict):
        """Create a company tenant + tenant_admin user; send email verification."""
        username = (data or {}).get("username")
        email = ((data or {}).get("email") or "").strip().lower()
        password = (data or {}).get("password")
        company_name = (data or {}).get("companyName") or (data or {}).get("company_name")
        if not all([username, email, password, company_name]):
            raise ValidationError("username, email, password, companyName are required")
        slug = (
            (data or {}).get("slug")
            or company_name.lower().replace(" ", "-").replace("_", "-")[:48]
        )
        with get_session() as session:
            ensure_auth_schema(session)
            if session.exec(
                select(User).where((User.username == username) | (User.email == email))
            ).first():
                raise ValidationError("Username or email already exists")
            if session.exec(select(Tenant).where(Tenant.slug == slug)).first():
                raise ValidationError("Company slug already exists")
            role = session.exec(select(Role).where(Role.role_name == "tenant_admin")).first()
            if not role:
                raise AppError("Roles not seeded — run scripts/seed.py", 500, "SETUP")
            training = TenantTrainingSchema(
                company=CompanySection(legal_name=company_name, display_name=company_name),
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
            session.flush()
            user = User(
                username=username,
                email=email,
                password=bcrypt.hash(password),
                role_id=role.role_id,
                tenant_id=tenant.tenant_id,
                email_verified_at=None,
                token_version=0,
            )
            session.add(user)
            session.flush()

            raw_verify = issue_token(
                session, user=user, purpose=PURPOSE_EMAIL_VERIFY
            )
            mail = send_verification_email(to_email=email, raw_token=raw_verify)
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
                    "message": "Registered — check your email to verify your account",
                    **tokens,
                    "user": _auth_user_dict(user, role, permission_codes, modules),
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
                user.email_verified_at = datetime.utcnow()
                user.updated_at = datetime.utcnow()
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
            user.updated_at = datetime.utcnow()
            # Optional: mark email verified on successful reset via known mailbox
            if user.email_verified_at is None:
                user.email_verified_at = datetime.utcnow()
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
