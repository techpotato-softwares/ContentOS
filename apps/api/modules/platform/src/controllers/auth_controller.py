from __future__ import annotations

import json
import re
import secrets
from passlib.hash import bcrypt
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from decorators import Controller, Post, Get
from decorators.auth_decorators import ApiPublic, RequirePermission
from database import get_session
from database.models import User, Role, RolePermission, Permission, Tenant
from utils.webtoken import generate_tokens
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
    """Idempotently create permissions + roles; return tenant_admin for membership."""
    perm_map: dict[str, int] = {}
    for code, name in _PERMS:
        existing = session.exec(
            select(Permission).where(Permission.permission_code == code)
        ).first()
        if not existing:
            existing = Permission(
                permission_code=code, permission_name=name, description=name
            )
            session.add(existing)
            session.flush()
        perm_map[code] = existing.permission_id  # type: ignore[assignment]

    tenant_admin: Role | None = None
    for role_name, codes in _ROLES.items():
        role = session.exec(select(Role).where(Role.role_name == role_name)).first()
        if not role:
            role = Role(role_name=role_name, description=role_name)
            session.add(role)
            session.flush()
        for code in codes:
            pid = perm_map[code]
            rp = session.exec(
                select(RolePermission).where(
                    RolePermission.role_id == role.role_id,
                    RolePermission.permission_id == pid,
                )
            ).first()
            if not rp:
                session.add(RolePermission(role_id=role.role_id, permission_id=pid))
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
        password = body.get("password") or ""
        company_name = (
            body.get("companyName") or body.get("company_name") or ""
        ).strip()
        if not username:
            raise ValidationError("username is required")
        if not email:
            raise ValidationError("email is required")
        if not password:
            raise ValidationError("password is required")
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
            except IntegrityError:
                session.rollback()
                # Unique violations → human-readable 409, never a stack trace
                raise ConflictError(
                    "An account with this email or username already exists."
                )
            except Exception:
                session.rollback()
                raise

    @Get("/me")
    @RequirePermission("agent:chat", "tenant:admin", "admin:tenants", "admin")
    def me(self, user=None):
        return create_success_response({"user": user})
