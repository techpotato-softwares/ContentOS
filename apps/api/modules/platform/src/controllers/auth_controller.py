from __future__ import annotations
import json
from passlib.hash import bcrypt
from sqlmodel import select
from decorators import Controller, Post, Get
from decorators.auth_decorators import ApiPublic, RequirePermission
from database import get_session
from database.models import User, Role, RolePermission, Permission, Tenant
from utils.webtoken import generate_tokens
from middleware.error_handler import AppError, ValidationError, create_success_response
from training.schema import TenantTrainingSchema, CompanySection, BrandVisualSection


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
    return {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "role": role.role_name if role else None,
        "tenantId": user.tenant_id,
        "permissions": permissions,
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
                    "user": {
                        "userId": user.user_id,
                        "username": user.username,
                        "email": user.email,
                        "roleName": role.role_name if role else None,
                        "tenantId": user.tenant_id,
                        "permissions": permission_codes,
                        "modulesEnabled": modules,
                    },
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
        """Create a company tenant + tenant_admin user."""
        username = (data or {}).get("username")
        email = (data or {}).get("email")
        password = (data or {}).get("password")
        company_name = (data or {}).get("companyName") or (data or {}).get("company_name")
        if not all([username, email, password, company_name]):
            raise ValidationError("username, email, password, companyName are required")
        slug = (
            (data or {}).get("slug")
            or company_name.lower().replace(" ", "-").replace("_", "-")[:48]
        )
        with get_session() as session:
            if session.exec(select(User).where((User.username == username) | (User.email == email))).first():
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
                modules_enabled=json.dumps(["platform", "tenants", "agent", "publishing"]),
                training_json=training.model_dump_json(),
                ui_mode="platform",
                app_display_name=company_name,
                onboarding_json=json.dumps(
                    {
                        "version": 1,
                        "status": "pending",
                        "steps": {
                            "linkedin": False,
                            "training": False,
                            "generate": False,
                            "publish": False,
                        },
                        "skippedAt": None,
                        "completedAt": None,
                        "updatedAt": None,
                    }
                ),
            )
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
            user = User(
                username=username,
                email=email,
                password=bcrypt.hash(password),
                role_id=role.role_id,
                tenant_id=tenant.tenant_id,
            )
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
                    "message": "Registered",
                    **tokens,
                    "user": {
                        "userId": user.user_id,
                        "username": user.username,
                        "email": user.email,
                        "roleName": role.role_name if role else None,
                        "tenantId": user.tenant_id,
                        "permissions": permission_codes,
                        "modulesEnabled": modules,
                    },
                    "tenant": {"tenantId": tenant.tenant_id, "name": tenant.name, "slug": tenant.slug},
                },
                201,
            )

    @Get("/me")
    @RequirePermission("agent:chat", "tenant:admin", "admin:tenants", "admin")
    def me(self, user=None):
        return create_success_response({"user": user})
