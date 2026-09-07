"""Integration tests for production self-serve signup (POST /api/register).

Seed scripts are NOT used — registration must bootstrap RBAC and create
Tenant + User + tenant_admin membership atomically.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ["IS_LOCAL"] = "true"
os.environ["APP_NAME"] = "contentos"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret-at-least-32-chars-xx"
os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, select

import database as db_mod
from database.models import User, Tenant, Role
from middleware.error_handler import ConflictError, ValidationError, AppError
from utils.webtoken import verify_access_token
from modules.platform.src.controllers.auth_controller import AuthController


@pytest.fixture()
def db_session(tmp_path):
    """Isolated SQLite DB per test; patches get_session / get_engine."""
    url = f"sqlite:///{tmp_path / 'register.db'}"
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

    with patch.object(db_mod, "get_session", _get_session), patch.object(
        db_mod, "get_engine", lambda: engine
    ), patch(
        "modules.platform.src.controllers.auth_controller.get_session", _get_session
    ):
        yield factory

    db_mod._engine = None
    db_mod._SessionLocal = None


def _unique(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _register(ctrl: AuthController, **overrides):
    base = {
        "username": _unique("user"),
        "email": f"{_unique('mail')}@example.com",
        "password": "SecurePass123!",
        "companyName": f"Acme {_unique('co')}",
    }
    base.update(overrides)
    return base, ctrl.register(base)


def test_register_creates_user_tenant_and_tenant_admin(db_session):
    ctrl = AuthController()
    payload, resp = _register(ctrl)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["success"] is True
    data = body["data"]
    assert data["user"]["email"] == payload["email"]
    assert data["user"]["roleName"] == "tenant_admin"
    assert data["user"]["tenantId"] is not None
    assert data["tenant"]["name"] == payload["companyName"]
    assert data["accessToken"]

    with db_session() as session:
        user = session.exec(select(User).where(User.email == payload["email"])).first()
        assert user is not None
        assert user.tenant_id == data["user"]["tenantId"]
        tenant = session.get(Tenant, user.tenant_id)
        assert tenant is not None
        assert tenant.name == payload["companyName"]
        role = session.get(Role, user.role_id)
        assert role is not None
        assert role.role_name == "tenant_admin"


def test_register_jwt_contains_tenant_and_role(db_session):
    ctrl = AuthController()
    _, resp = _register(ctrl)
    data = json.loads(resp["body"])["data"]
    claims = verify_access_token(data["accessToken"])
    assert claims.get("tenantId") == data["user"]["tenantId"]
    assert claims.get("role") == "tenant_admin"
    assert claims.get("userId") == data["user"]["userId"]


def test_login_after_register(db_session):
    ctrl = AuthController()
    payload, reg = _register(ctrl)
    login_resp = ctrl.login(
        {"username": payload["email"], "password": payload["password"]}
    )
    assert login_resp["statusCode"] == 200
    login_data = json.loads(login_resp["body"])["data"]
    claims = verify_access_token(login_data["accessToken"])
    assert claims.get("tenantId") is not None
    assert claims.get("role") == "tenant_admin"


def test_authenticated_agent_sessions_after_register(db_session):
    """Registered JWT can call an authenticated agent endpoint."""
    ctrl = AuthController()
    _, reg = _register(ctrl)
    data = json.loads(reg["body"])["data"]
    claims = verify_access_token(data["accessToken"])
    assert claims.get("tenantId")
    assert claims.get("role") == "tenant_admin"

    from modules.agent.src.controllers.agent_controller import AgentController

    agent = AgentController()
    with patch(
        "modules.agent.src.controllers.agent_controller.get_session",
        db_session,
    ):
        resp = agent.list_sessions(user=claims)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_duplicate_email_returns_409(db_session):
    ctrl = AuthController()
    email = f"{_unique('dup')}@example.com"
    _register(ctrl, email=email, username=_unique("a"))
    with pytest.raises(ConflictError) as exc:
        _register(ctrl, email=email, username=_unique("b"), companyName="Other Co")
    assert exc.value.status_code == 409
    assert "email" in exc.value.message.lower()
    # Envelope path via error handler should also be clean JSON
    from middleware.error_handler import create_error_response

    resp = create_error_response(exc.value)
    assert resp["statusCode"] == 409
    err = json.loads(resp["body"])["error"]
    assert err["code"] == "CONFLICT"
    assert "Traceback" not in err["message"]


def test_duplicate_username_returns_409(db_session):
    ctrl = AuthController()
    username = _unique("sameuser")
    _register(ctrl, username=username, email=f"{_unique('a')}@example.com")
    with pytest.raises(ConflictError) as exc:
        _register(
            ctrl,
            username=username,
            email=f"{_unique('b')}@example.com",
            companyName="Other Co",
        )
    assert exc.value.status_code == 409
    assert "username" in exc.value.message.lower()


def test_integrity_email_unique_maps_to_409():
    """PostgreSQL-style users.email unique violation → same 409 message."""
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    mock_exc = IntegrityError(
        "INSERT INTO users",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "ix_users_email"})(),
            },
        )(),
    )
    conflict = ac._user_conflict_from_integrity(mock_exc)
    assert conflict is not None
    assert conflict.status_code == 409
    assert conflict.message == "An account with this email or username already exists."


def test_integrity_sqlite_users_email_message_maps_to_409():
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    mock_exc = IntegrityError(
        "INSERT",
        {},
        Exception("UNIQUE constraint failed: users.email"),
    )
    conflict = ac._user_conflict_from_integrity(mock_exc)
    assert conflict is not None
    assert conflict.status_code == 409


def test_integrity_username_unique_maps_to_409():
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    mock_exc = IntegrityError(
        "INSERT",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "ix_users_username"})(),
            },
        )(),
    )
    conflict = ac._user_conflict_from_integrity(mock_exc)
    assert conflict is not None
    assert conflict.status_code == 409


def test_integrity_rbac_unique_not_409():
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    for name in ("ix_permissions_permission_code", "ix_roles_role_name"):
        mock_exc = IntegrityError(
            "INSERT",
            {},
            type(
                "O",
                (),
                {"pgcode": "23505", "diag": type("D", (), {"constraint_name": name})()},
            )(),
        )
        assert ac._user_conflict_from_integrity(mock_exc) is None


def test_integrity_tenant_slug_unique_not_409():
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    mock_exc = IntegrityError(
        "INSERT",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "ix_tenants_slug"})(),
            },
        )(),
    )
    assert ac._user_conflict_from_integrity(mock_exc) is None


def test_integrity_unknown_not_409():
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    mock_exc = IntegrityError(
        "INSERT",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "uq_something_else"})(),
            },
        )(),
    )
    assert ac._user_conflict_from_integrity(mock_exc) is None

    bare = IntegrityError("INSERT", {}, Exception("connection reset"))
    assert ac._user_conflict_from_integrity(bare) is None


def test_register_slug_integrity_error_not_mapped_to_409(db_session):
    """If tenants.slug unique fires, register must not return ConflictError 409."""
    ctrl = AuthController()
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    slug_exc = IntegrityError(
        "INSERT INTO tenants",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "ix_tenants_slug"})(),
            },
        )(),
    )

    calls = {"n": 0}
    original_ensure = ac._ensure_platform_rbac

    def ensure_then_fail(session):
        role = original_ensure(session)
        real_flush = session.flush

        def flusher(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise slug_exc
            return real_flush(*a, **k)

        session.flush = flusher  # type: ignore[method-assign]
        return role

    with patch.object(ac, "_ensure_platform_rbac", side_effect=ensure_then_fail):
        with pytest.raises(IntegrityError) as exc:
            ctrl.register(
                {
                    "username": _unique("slugrace"),
                    "email": f"{_unique('slug')}@example.com",
                    "password": "SecurePass123!",
                    "companyName": f"Slug Race {_unique('c')}",
                }
            )
        assert not isinstance(exc.value, ConflictError)
        assert ac._user_conflict_from_integrity(exc.value) is None


def test_register_rbac_integrity_error_not_mapped_to_409(db_session):
    ctrl = AuthController()
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    rbac_exc = IntegrityError(
        "INSERT INTO permissions",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type(
                    "D", (), {"constraint_name": "ix_permissions_permission_code"}
                )(),
            },
        )(),
    )

    with patch.object(ac, "_ensure_platform_rbac", side_effect=rbac_exc):
        with pytest.raises(IntegrityError) as exc:
            ctrl.register(
                {
                    "username": _unique("rbac"),
                    "email": f"{_unique('rbac')}@example.com",
                    "password": "SecurePass123!",
                    "companyName": f"RBAC {_unique('c')}",
                }
            )
        assert ac._user_conflict_from_integrity(exc.value) is None


def test_register_user_email_integrity_maps_to_409(db_session):
    """IntegrityError on users.email during register → ConflictError (not raw IntegrityError)."""
    ctrl = AuthController()
    from modules.platform.src.controllers import auth_controller as ac
    from sqlalchemy.exc import IntegrityError

    email_exc = IntegrityError(
        "INSERT INTO users",
        {},
        type(
            "O",
            (),
            {
                "pgcode": "23505",
                "diag": type("D", (), {"constraint_name": "ix_users_email"})(),
            },
        )(),
    )

    original_ensure = ac._ensure_platform_rbac
    calls = {"n": 0}

    def ensure_then_fail_on_user(session):
        role = original_ensure(session)
        real_flush = session.flush

        def flusher(*a, **k):
            calls["n"] += 1
            # 1 = tenant flush, 2 = user flush
            if calls["n"] >= 2:
                raise email_exc
            return real_flush(*a, **k)

        session.flush = flusher  # type: ignore[method-assign]
        return role

    with patch.object(ac, "_ensure_platform_rbac", side_effect=ensure_then_fail_on_user):
        with pytest.raises(ConflictError) as exc:
            ctrl.register(
                {
                    "username": _unique("emailrace"),
                    "email": f"{_unique('emailrace')}@example.com",
                    "password": "SecurePass123!",
                    "companyName": f"Email Race {_unique('c')}",
                }
            )
        assert exc.value.status_code == 409
        assert exc.value.message == "An account with this email or username already exists."


def test_missing_company_name_validation(db_session):
    ctrl = AuthController()
    with pytest.raises(ValidationError) as exc:
        ctrl.register(
            {
                "username": _unique("x"),
                "email": f"{_unique('x')}@example.com",
                "password": "SecurePass123!",
            }
        )
    assert exc.value.status_code == 400
    assert "companyName" in exc.value.message


def test_register_rejects_empty_password(db_session):
    ctrl = AuthController()
    for pwd in (None, ""):
        with pytest.raises(ValidationError) as exc:
            ctrl.register(
                {
                    "username": _unique("pw"),
                    "email": f"{_unique('pw')}@example.com",
                    "password": pwd,
                    "companyName": f"Co {_unique('c')}",
                }
            )
        assert exc.value.status_code == 400
        assert exc.value.message == "password is required"


def test_register_rejects_short_passwords(db_session):
    ctrl = AuthController()
    for pwd in ("a", "1234567"):
        with pytest.raises(ValidationError) as exc:
            ctrl.register(
                {
                    "username": _unique("short"),
                    "email": f"{_unique('short')}@example.com",
                    "password": pwd,
                    "companyName": f"Co {_unique('c')}",
                }
            )
        assert exc.value.status_code == 400
        assert exc.value.message == "password must be at least 8 characters"
        # Must not echo the submitted password (beyond accidental substring overlap)
        if len(pwd) > 1:
            assert pwd not in exc.value.message


def test_register_accepts_eight_char_password(db_session):
    ctrl = AuthController()
    payload, resp = _register(ctrl, password="12345678")
    assert resp["statusCode"] == 201
    login = ctrl.login({"username": payload["email"], "password": "12345678"})
    assert login["statusCode"] == 200


def test_register_accepts_strong_password(db_session):
    ctrl = AuthController()
    strong = "SecurePass123!"
    payload, resp = _register(ctrl, password=strong)
    assert resp["statusCode"] == 201
    login = ctrl.login({"username": payload["email"], "password": strong})
    assert login["statusCode"] == 200


def test_registration_failure_rolls_back_no_orphans(db_session):
    """If user creation fails after tenant flush, nothing is committed."""
    ctrl = AuthController()
    email = f"{_unique('fail')}@example.com"
    username = _unique("failuser")
    company = f"Fail Co {_unique('c')}"

    with patch(
        "modules.platform.src.controllers.auth_controller.bcrypt.hash",
        side_effect=RuntimeError("simulated user create failure"),
    ):
        with pytest.raises(RuntimeError, match="simulated"):
            ctrl.register(
                {
                    "username": username,
                    "email": email,
                    "password": "SecurePass123!",
                    "companyName": company,
                }
            )

    with db_session() as session:
        assert session.exec(select(User).where(User.email == email)).first() is None
        assert session.exec(select(User).where(User.username == username)).first() is None
        assert session.exec(select(Tenant).where(Tenant.name == company)).first() is None


def test_slug_collision_derives_unique_slug(db_session):
    ctrl = AuthController()
    company = "Same Name Co"
    _, first = _register(ctrl, companyName=company, username=_unique("s1"))
    _, second = _register(ctrl, companyName=company, username=_unique("s2"))
    slug1 = json.loads(first["body"])["data"]["tenant"]["slug"]
    slug2 = json.loads(second["body"])["data"]["tenant"]["slug"]
    assert slug1 != slug2
