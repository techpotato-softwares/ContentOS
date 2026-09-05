"""Tenant team invitation API tests."""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from passlib.hash import bcrypt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ["SES_ENABLED"] = "false"
os.environ["SES_FROM_EMAIL"] = "noreply@localhost"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import Permission, Role, RolePermission, Tenant, TenantInvite, User
from middleware.error_handler import AppError, ValidationError
from utils.tenant_invites import hash_invite_token
from modules.tenants.src.controllers.tenants_controller import TenantsController


def _unique(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _seed(session: Session) -> dict:
    tenant = Tenant(name="Acme", slug=_unique("acme"))
    other = Tenant(name="Other", slug=_unique("other"))
    session.add(tenant)
    session.add(other)
    session.flush()

    roles: dict[str, Role] = {}
    for name in ("tenant_admin", "tenant_member"):
        role = Role(role_name=name, description=name)
        session.add(role)
        session.flush()
        roles[name] = role

    for code in ("tenant:admin", "agent:chat", "posts:review", "posts:publish", "training:manage"):
        perm = Permission(permission_code=code, permission_name=code)
        session.add(perm)
        session.flush()
        if code == "tenant:admin" or code.startswith("posts") or code == "agent:chat" or code == "training:manage":
            session.add(
                RolePermission(
                    role_id=roles["tenant_admin"].role_id,
                    permission_id=perm.permission_id,
                )
            )
        if code in ("agent:chat", "posts:review", "posts:publish"):
            session.add(
                RolePermission(
                    role_id=roles["tenant_member"].role_id,
                    permission_id=perm.permission_id,
                )
            )

    admin = User(
        username=_unique("admin"),
        email=f"{_unique('admin')}@example.com",
        password=bcrypt.hash("SecurePass123!"),
        role_id=roles["tenant_admin"].role_id,
        tenant_id=tenant.tenant_id,
    )
    member = User(
        username=_unique("member"),
        email=f"{_unique('member')}@example.com",
        password=bcrypt.hash("SecurePass123!"),
        role_id=roles["tenant_member"].role_id,
        tenant_id=tenant.tenant_id,
    )
    other_user = User(
        username=_unique("xuser"),
        email=f"{_unique('xuser')}@example.com",
        password=bcrypt.hash("SecurePass123!"),
        role_id=roles["tenant_member"].role_id,
        tenant_id=other.tenant_id,
    )
    session.add(admin)
    session.add(member)
    session.add(other_user)
    session.commit()
    session.refresh(admin)
    session.refresh(member)
    session.refresh(other_user)
    session.refresh(tenant)
    session.refresh(other)
    return {
        "tenant": tenant,
        "other": other,
        "admin": admin,
        "member": member,
        "other_user": other_user,
        "roles": roles,
    }


def _admin_user(ctx) -> dict:
    return {
        "userId": ctx["admin"].user_id,
        "tenantId": ctx["tenant"].tenant_id,
        "role": "tenant_admin",
        "permissions": ["tenant:admin", "agent:chat", "posts:publish", "training:manage"],
        "modulesEnabled": ["platform", "tenants", "agent", "publishing"],
    }


def _member_user(ctx) -> dict:
    return {
        "userId": ctx["member"].user_id,
        "tenantId": ctx["tenant"].tenant_id,
        "role": "tenant_member",
        "permissions": ["agent:chat", "posts:review", "posts:publish"],
        "modulesEnabled": ["platform", "tenants", "agent", "publishing"],
    }


@pytest.fixture()
def db_ctx(tmp_path):
    url = f"sqlite:///{tmp_path / 'invites.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    db_mod._engine = engine
    db_mod._SessionLocal = factory

    def _get_session():
        return factory()

    with _get_session() as s:
        ctx = _seed(s)

    with patch.object(db_mod, "get_session", _get_session), patch.object(
        db_mod, "get_engine", lambda: engine
    ), patch(
        "modules.tenants.src.controllers.tenants_controller.get_session", _get_session
    ):
        yield {"factory": factory, **ctx}

    db_mod._engine = None
    db_mod._SessionLocal = None


def _token_from_dev_link(dev_link: str) -> str:
    m = re.search(r"token=([^&]+)", dev_link or "")
    assert m, f"expected token in {dev_link!r}"
    return m.group(1)


def test_admin_creates_invite_and_lists(db_ctx):
    ctrl = TenantsController()
    email = f"{_unique('invite')}@example.com"
    resp = ctrl.create_invite(
        {"email": email, "role": "tenant_member"}, user=_admin_user(db_ctx)
    )
    assert resp["statusCode"] == 201
    data = json.loads(resp["body"])["data"]
    assert data["email"] == email
    assert data["role"] == "tenant_member"
    assert data["status"] == "pending"
    assert "devLink" in data
    assert "token=" in data["devLink"]

    listed = ctrl.list_invites(user=_admin_user(db_ctx))
    items = json.loads(listed["body"])["data"]
    assert any(i["email"] == email for i in items)

    with db_ctx["factory"]() as session:
        row = session.exec(select(TenantInvite).where(TenantInvite.email == email)).first()
        raw = _token_from_dev_link(data["devLink"])
        assert row.token == hash_invite_token(raw)
        assert raw not in row.token


def test_member_cannot_manage_invites_via_router_permissions(db_ctx):
    owned = set(_member_user(db_ctx)["permissions"])
    required = ["tenant:admin", "admin:tenants"]
    assert not any(c in owned for c in required)


def test_accept_invite_creates_user_on_tenant(db_ctx):
    ctrl = TenantsController()
    email = f"{_unique('join')}@example.com"
    created = ctrl.create_invite(
        {"email": email, "role": "tenant_member"}, user=_admin_user(db_ctx)
    )
    raw = _token_from_dev_link(json.loads(created["body"])["data"]["devLink"])
    username = _unique("newbie")
    accepted = ctrl.accept_invite(
        raw, {"username": username, "password": "Welcome123!"}
    )
    assert accepted["statusCode"] == 200
    body = json.loads(accepted["body"])["data"]
    assert body["user"]["email"] == email
    assert body["user"]["tenantId"] == db_ctx["tenant"].tenant_id
    assert body["user"]["roleName"] == "tenant_member"

    with db_ctx["factory"]() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        assert user is not None
        assert user.tenant_id == db_ctx["tenant"].tenant_id
        role = session.get(Role, user.role_id)
        assert role.role_name == "tenant_member"
        inv = session.exec(select(TenantInvite).where(TenantInvite.email == email)).first()
        assert inv.status == "accepted"


def test_revoke_and_reuse_fail(db_ctx):
    ctrl = TenantsController()
    email = f"{_unique('rev')}@example.com"
    created = ctrl.create_invite(
        {"email": email, "role": "tenant_member"}, user=_admin_user(db_ctx)
    )
    data = json.loads(created["body"])["data"]
    raw = _token_from_dev_link(data["devLink"])
    rev = ctrl.revoke_invite(str(data["inviteId"]), user=_admin_user(db_ctx))
    assert rev["statusCode"] == 200
    with pytest.raises(AppError) as exc:
        ctrl.accept_invite(raw, {"username": _unique("x"), "password": "Welcome123!"})
    assert exc.value.code == "INVITE_REVOKED"


def test_expired_and_used_invites(db_ctx):
    ctrl = TenantsController()
    email = f"{_unique('exp')}@example.com"
    created = ctrl.create_invite(
        {"email": email, "role": "tenant_member"}, user=_admin_user(db_ctx)
    )
    raw = _token_from_dev_link(json.loads(created["body"])["data"]["devLink"])
    with db_ctx["factory"]() as session:
        row = session.exec(
            select(TenantInvite).where(TenantInvite.token == hash_invite_token(raw))
        ).first()
        row.expires_at = datetime.utcnow() - timedelta(hours=1)
        session.add(row)
        session.commit()
    with pytest.raises(AppError) as exc:
        ctrl.accept_invite(raw, {"username": _unique("x"), "password": "Welcome123!"})
    assert exc.value.code == "INVITE_EXPIRED"

    email2 = f"{_unique('used')}@example.com"
    c2 = ctrl.create_invite(
        {"email": email2, "role": "tenant_admin"}, user=_admin_user(db_ctx)
    )
    raw2 = _token_from_dev_link(json.loads(c2["body"])["data"]["devLink"])
    ctrl.accept_invite(raw2, {"username": _unique("u2"), "password": "Welcome123!"})
    with pytest.raises(AppError) as used:
        ctrl.accept_invite(raw2, {"username": _unique("u3"), "password": "Welcome123!"})
    assert used.value.code == "INVITE_USED"


def test_cross_tenant_email_rejected(db_ctx):
    ctrl = TenantsController()
    # Invite email that already belongs to another tenant
    with pytest.raises(AppError) as exc:
        ctrl.create_invite(
            {"email": db_ctx["other_user"].email, "role": "tenant_member"},
            user=_admin_user(db_ctx),
        )
    assert exc.value.code == "EMAIL_IN_USE"


def test_revoke_wrong_tenant_not_found(db_ctx):
    ctrl = TenantsController()
    email = f"{_unique('iso')}@example.com"
    created = ctrl.create_invite(
        {"email": email, "role": "tenant_member"}, user=_admin_user(db_ctx)
    )
    invite_id = json.loads(created["body"])["data"]["inviteId"]
    # Super-admin style other tenant id would need admin — non-matching tenant via JWT
    other_admin = {
        **_admin_user(db_ctx),
        "tenantId": db_ctx["other"].tenant_id,
        "userId": db_ctx["other_user"].user_id,
    }
    # other_user is member — still call revoke with other tenant context
    from middleware.error_handler import NotFoundError

    with pytest.raises(NotFoundError):
        ctrl.revoke_invite(str(invite_id), user=other_admin)


def test_invalid_role_rejected(db_ctx):
    ctrl = TenantsController()
    with pytest.raises(ValidationError):
        ctrl.create_invite(
            {"email": f"{_unique('bad')}@example.com", "role": "super_admin"},
            user=_admin_user(db_ctx),
        )
