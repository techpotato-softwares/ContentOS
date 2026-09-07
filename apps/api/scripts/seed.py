#!/usr/bin/env python3
"""Local/dev database bootstrap — NOT required for production self-serve signup.

Creates tables and seeds demo roles, permissions, superadmin/demo users.
Production tenants sign up via POST /api/register (transactional; bootstraps RBAC).
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

# Load .env if present
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

os.environ.setdefault("IS_LOCAL", "true")
os.environ.setdefault("APP_NAME", "contentos")

from passlib.hash import bcrypt
from sqlmodel import select
from database import init_db, get_session
import database.models  # noqa: F401
from database.models import Tenant, User, Role, Permission, RolePermission
from training.schema import TenantTrainingSchema, CompanySection, BrandVisualSection
from utils.app_env import is_production
from utils.seed_credentials import SEED_PASSWORD
import json

PERMS = [
    ("admin:tenants", "Manage all tenants"),
    ("training:manage", "Edit training schema"),
    ("tenant:admin", "Tenant administration"),
    ("agent:chat", "Agent chat & generate"),
    ("posts:review", "Review posts"),
    ("posts:publish", "Publish to LinkedIn"),
    ("admin", "Legacy admin"),
]

ROLES = {
    "super_admin": [p[0] for p in PERMS],
    "tenant_admin": [
        "training:manage",
        "tenant:admin",
        "agent:chat",
        "posts:review",
        "posts:publish",
    ],
    "tenant_member": ["agent:chat", "posts:review", "posts:publish"],
}


def main():
    init_db()
    # Ensure newer columns exist on existing DBs
    try:
        from sqlalchemy import text
        from database import get_engine

        with get_engine().begin() as conn:
            for col, typ in [
                ("layout_json", "TEXT"),
                ("score_json", "TEXT"),
                ("source_type", "VARCHAR"),
                ("source_ref", "TEXT"),
                ("ab_label", "VARCHAR"),
                ("scheduled_at", "TIMESTAMP"),
            ]:
                try:
                    conn.execute(
                        text(f"ALTER TABLE content_posts ADD COLUMN IF NOT EXISTS {col} {typ}")
                    )
                except Exception:
                    pass
            for col, typ in [
                ("account_kind", "VARCHAR DEFAULT 'member'"),
                ("author_urn", "VARCHAR"),
                ("metadata_json", "TEXT"),
            ]:
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS {col} {typ}"
                        )
                    )
                except Exception:
                    pass
            try:
                conn.execute(
                    text(
                        "UPDATE social_accounts SET account_kind = 'member' "
                        "WHERE account_kind IS NULL OR account_kind = ''"
                    )
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text("ALTER TABLE social_accounts DROP CONSTRAINT IF EXISTS uq_tenant_platform")
                )
            except Exception:
                pass
            try:
                conn.execute(
                    text(
                        "ALTER TABLE social_accounts ADD CONSTRAINT uq_tenant_platform_kind "
                        "UNIQUE (tenant_id, platform, account_kind)"
                    )
                )
            except Exception:
                pass
    except Exception:
        pass
    with get_session() as session:
        perm_map: dict[str, int] = {}
        for code, name in PERMS:
            existing = session.exec(select(Permission).where(Permission.permission_code == code)).first()
            if not existing:
                existing = Permission(permission_code=code, permission_name=name, description=name)
                session.add(existing)
                session.commit()
                session.refresh(existing)
            perm_map[code] = existing.permission_id  # type: ignore

        role_map: dict[str, int] = {}
        for role_name, codes in ROLES.items():
            role = session.exec(select(Role).where(Role.role_name == role_name)).first()
            if not role:
                role = Role(role_name=role_name, description=role_name)
                session.add(role)
                session.commit()
                session.refresh(role)
            role_map[role_name] = role.role_id  # type: ignore
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
            session.commit()

        # Platform tenant for super admin (ui platform)
        platform = session.exec(select(Tenant).where(Tenant.slug == "contentos-platform")).first()
        if not platform:
            training = TenantTrainingSchema(
                company=CompanySection(
                    legal_name="TechPotato Softwares LLP",
                    display_name="ContentOS",
                    industry="SaaS",
                    one_liner="AI content OS for B2B LinkedIn growth",
                ),
                brand_visual=BrandVisualSection(ui_mode="platform"),
            )
            platform = Tenant(
                name="ContentOS Platform",
                slug="contentos-platform",
                modules_enabled=json.dumps(["platform", "tenants", "agent", "publishing"]),
                training_json=training.model_dump_json(),
                ui_mode="platform",
            )
            session.add(platform)
            session.commit()
            session.refresh(platform)

        demo = session.exec(select(Tenant).where(Tenant.slug == "demo-co")).first()
        if not demo:
            training = TenantTrainingSchema(
                company=CompanySection(
                    legal_name="Demo Company Pvt Ltd",
                    display_name="Demo Co",
                    industry="B2B SaaS",
                    one_liner="Demo tenant for ContentOS LinkedIn posts",
                    website="https://example.com",
                ),
                brand_visual=BrandVisualSection(ui_mode="platform"),
            )
            demo = Tenant(
                name="Demo Co",
                slug="demo-co",
                modules_enabled=json.dumps(["platform", "tenants", "agent", "publishing"]),
                training_json=training.model_dump_json(),
                ui_mode="platform",
                app_display_name="Demo Co",
            )
            session.add(demo)
            session.commit()
            session.refresh(demo)

        if is_production():
            session.commit()
            print(
                "ContentOS DB initialized (production): roles/tenants only — "
                "seed users/passwords are disabled when APP_ENV=production."
            )
            return

        pwd = bcrypt.hash(SEED_PASSWORD)
        if not session.exec(select(User).where(User.username == "superadmin")).first():
            session.add(
                User(
                    username="superadmin",
                    email="superadmin@contentos.local",
                    password=pwd,
                    role_id=role_map["super_admin"],
                    tenant_id=platform.tenant_id,
                )
            )
        if not session.exec(select(User).where(User.username == "demo")).first():
            session.add(
                User(
                    username="demo",
                    email="demo@demo-co.local",
                    password=pwd,
                    role_id=role_map["tenant_admin"],
                    tenant_id=demo.tenant_id,
                )
            )
        session.commit()
    print(f"ContentOS DB initialized. Users: superadmin / demo  password: {SEED_PASSWORD}")


if __name__ == "__main__":
    main()
