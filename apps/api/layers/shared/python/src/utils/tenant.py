"""Tenant isolation helpers — always scope by tenant_id from JWT (or explicit admin target)."""
from __future__ import annotations
from typing import Any
from middleware.error_handler import AppError, ForbiddenError


SUPER_ADMIN_ROLE = "super_admin"


def is_super_admin(user: dict | None) -> bool:
    if not user:
        return False
    role = (user.get("role") or "").lower()
    perms = set(user.get("permissions") or [])
    return role == SUPER_ADMIN_ROLE or "admin:tenants" in perms


def require_user(user: dict | None) -> dict:
    if not user or not user.get("userId"):
        raise AppError("Unauthenticated", 401, "UNAUTHORIZED")
    return user


def resolve_tenant_id(user: dict | None, requested_tenant_id: int | None = None) -> int:
    """Return tenant_id for data access. Super admin may pass explicit tenantId."""
    u = require_user(user)
    if requested_tenant_id is not None:
        if not is_super_admin(u):
            raise ForbiddenError("Only super admin can access another tenant")
        return int(requested_tenant_id)
    tid = u.get("tenantId") if u.get("tenantId") is not None else u.get("tenant_id")
    if tid is None:
        raise ForbiddenError("User has no tenant context")
    return int(tid)


def assert_same_tenant(user: dict | None, resource_tenant_id: int) -> None:
    u = require_user(user)
    if is_super_admin(u):
        return
    tid = u.get("tenantId") if u.get("tenantId") is not None else u.get("tenant_id")
    if tid is None or int(tid) != int(resource_tenant_id):
        raise ForbiddenError("Cross-tenant access denied")


def tenant_s3_prefix(tenant_id: int) -> str:
    return f"tenants/{int(tenant_id)}/posts"


def write_audit(
    session: Any,
    *,
    tenant_id: int | None,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    from database.models import AuditLog

    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
        )
    )
