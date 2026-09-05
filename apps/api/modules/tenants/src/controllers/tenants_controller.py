from __future__ import annotations
import json
from datetime import datetime
from passlib.hash import bcrypt
from sqlmodel import select
from decorators import Controller, Get, Post, Put, Delete
from decorators.auth_decorators import RequirePermission, RequireModule, ApiPublic
from database import get_session
from database.models import Tenant, TrainingDocument, User, Role, TenantInvite
from middleware.error_handler import (
    AppError,
    NotFoundError,
    ValidationError,
    create_success_response,
)
from utils.tenant import resolve_tenant_id, is_super_admin, require_user, write_audit
from utils.tenant_invites import (
    STATUS_ACCEPTED,
    STATUS_PENDING,
    STATUS_REVOKED,
    assert_invite_acceptable,
    ensure_invite_schema,
    invite_public_dict,
    is_local,
    issue_invite_token,
    load_invite_by_raw_token,
)
from utils.invite_email import send_tenant_invite_email
from training.schema import (
    parse_training,
    render_context_pack,
    resolve_ui_theme,
    TenantTrainingSchema,
    DocumentRef,
    CompanySection,
    BrandVisualSection,
)


def _tenant_dict(t: Tenant) -> dict:
    return {
        "tenantId": t.tenant_id,
        "name": t.name,
        "slug": t.slug,
        "uiMode": t.ui_mode,
        "appDisplayName": t.app_display_name,
        "logoUrl": t.logo_url,
        "primaryColor": t.primary_color,
        "secondaryColor": t.secondary_color,
        "accentColor": t.accent_color,
        "contextPackVersion": t.context_pack_version,
        "isActive": t.is_active,
        "modulesEnabled": json.loads(t.modules_enabled or "[]"),
    }


def _apply_brand_columns(tenant: Tenant, training: TenantTrainingSchema) -> None:
    b = training.brand_visual
    tenant.logo_url = b.logo_url or tenant.logo_url
    tenant.primary_color = b.primary_color or tenant.primary_color
    tenant.secondary_color = b.secondary_color or tenant.secondary_color
    tenant.accent_color = b.accent_color or tenant.accent_color
    tenant.app_display_name = b.app_display_name or training.company.display_name or tenant.app_display_name
    # Only white_label when complete; else force platform
    from training.schema import is_white_label_complete

    if is_white_label_complete(b):
        tenant.ui_mode = "white_label"
    else:
        tenant.ui_mode = "platform"
        training.brand_visual.ui_mode = "platform"


def _rebuild_pack(session, tenant: Tenant) -> str:
    training = parse_training(tenant.training_json)
    docs = session.exec(
        select(TrainingDocument).where(
            TrainingDocument.tenant_id == tenant.tenant_id,
            TrainingDocument.is_active == True,
        )
    ).all()
    extra = [
        DocumentRef(title=d.title, category=d.category, body=d.body, priority=d.priority)  # type: ignore
        for d in docs
    ]
    pack = render_context_pack(training, extra)
    tenant.context_pack_cached = pack
    tenant.context_pack_version = (tenant.context_pack_version or 0) + 1
    tenant.updated_at = datetime.utcnow()
    session.add(tenant)
    return pack


@Controller(path="/api", lambda_name="tenants")
class TenantsController:
    @Get("/admin/tenants")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants")
    def list_tenants(self, user=None):
        require_user(user)
        if not is_super_admin(user):
            raise ValidationError("Forbidden")
        with get_session() as session:
            rows = session.exec(select(Tenant).where(Tenant.is_active == True)).all()
            return create_success_response([_tenant_dict(t) for t in rows])

    @Post("/admin/tenants")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants")
    def create_tenant(self, data: dict, user=None):
        require_user(user)
        name = (data or {}).get("name")
        slug = (data or {}).get("slug") or (name or "").lower().replace(" ", "-")
        if not name or not slug:
            raise ValidationError("name is required")
        with get_session() as session:
            if session.exec(select(Tenant).where(Tenant.slug == slug)).first():
                raise ValidationError("slug exists")
            training = TenantTrainingSchema(
                company=CompanySection(legal_name=name, display_name=name),
                brand_visual=BrandVisualSection(ui_mode="platform"),
            )
            t = Tenant(
                name=name,
                slug=slug,
                modules_enabled=json.dumps(["platform", "tenants", "agent", "publishing"]),
                training_json=training.model_dump_json(),
                ui_mode="platform",
                app_display_name=name,
            )
            session.add(t)
            session.commit()
            session.refresh(t)
            write_audit(
                session,
                tenant_id=t.tenant_id,
                actor_user_id=user.get("userId"),
                action="tenant.create",
                resource_type="tenant",
                resource_id=str(t.tenant_id),
            )
            session.commit()
            return create_success_response(_tenant_dict(t), 201)

    @Get("/tenants/me")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "training:manage", "agent:chat", "admin:tenants")
    def get_my_tenant(self, user=None, query: dict | None = None):
        q = query or {}
        requested = int(q["tenantId"]) if q.get("tenantId") else None
        tid = resolve_tenant_id(user, requested)
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            return create_success_response(_tenant_dict(t))

    @Get("/tenants/me/theme")
    @RequireModule("tenants")
    @RequirePermission("agent:chat", "tenant:admin", "training:manage", "admin:tenants")
    def get_theme(self, user=None, query: dict | None = None):
        q = query or {}
        requested = int(q["tenantId"]) if q.get("tenantId") else None
        tid = resolve_tenant_id(user, requested)
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            training = parse_training(t.training_json)
            theme = resolve_ui_theme(
                training,
                {
                    "primary_color": t.primary_color,
                    "secondary_color": t.secondary_color,
                    "accent_color": t.accent_color,
                    "logo_url": t.logo_url,
                    "app_display_name": t.app_display_name,
                    "ui_mode": t.ui_mode,
                },
            )
            return create_success_response(theme)

    @Get("/tenants/me/training")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "tenant:admin", "admin:tenants")
    def get_training(self, user=None, query: dict | None = None):
        q = query or {}
        requested = int(q["tenantId"]) if q.get("tenantId") else None
        tid = resolve_tenant_id(user, requested)
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            return create_success_response(parse_training(t.training_json).model_dump())

    @Put("/tenants/me/training")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def put_training(self, data: dict, user=None, query: dict | None = None):
        q = query or {}
        requested = int(q["tenantId"]) if q.get("tenantId") else None
        # also allow tenantId in body for admin
        if (data or {}).get("tenantId") and is_super_admin(user):
            requested = int(data["tenantId"])
        tid = resolve_tenant_id(user, requested)
        try:
            training = TenantTrainingSchema.model_validate(data or {})
        except Exception as e:
            raise ValidationError(f"Invalid training schema: {e}")
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            _apply_brand_columns(t, training)
            t.training_json = training.model_dump_json()
            pack = _rebuild_pack(session, t)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=(user or {}).get("userId"),
                action="training.update",
                resource_type="tenant",
                resource_id=str(tid),
            )
            session.commit()
            return create_success_response(
                {"training": training.model_dump(), "contextPackVersion": t.context_pack_version, "packPreviewLen": len(pack)}
            )

    # Admin path aliases
    @Get("/admin/tenants/{tenantId}/training")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants")
    def admin_get_training(self, tenantId: str, user=None):
        return self.get_training(user=user, query={"tenantId": tenantId})

    @Put("/admin/tenants/{tenantId}/training")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants")
    def admin_put_training(self, tenantId: str, data: dict, user=None):
        data = {**(data or {}), "tenantId": int(tenantId)}
        return self.put_training(data=data, user=user, query={"tenantId": tenantId})

    @Get("/admin/tenants/{tenantId}/training/preview")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants", "training:manage")
    def training_preview(self, tenantId: str, user=None):
        tid = resolve_tenant_id(user, int(tenantId))
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            training = parse_training(t.training_json)
            pack = t.context_pack_cached or _rebuild_pack(session, t)
            session.commit()
            return create_success_response(
                {"training": training.model_dump(), "contextPack": pack, "version": t.context_pack_version}
            )

    @Post("/admin/tenants/{tenantId}/training/rebuild")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants", "training:manage")
    def training_rebuild(self, tenantId: str, user=None):
        tid = resolve_tenant_id(user, int(tenantId))
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            pack = _rebuild_pack(session, t)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=(user or {}).get("userId"),
                action="training.rebuild",
                resource_type="tenant",
                resource_id=str(tid),
            )
            session.commit()
            return create_success_response({"version": t.context_pack_version, "length": len(pack)})

    @Post("/tenants/me/brand/logo")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def upload_logo(self, data: dict, user=None, query: dict | None = None):
        """Accept base64 image JSON (works with Lambda-style body). Max ~2MB decoded."""
        import base64
        from pathlib import Path

        q = query or {}
        requested = None
        if (data or {}).get("tenantId"):
            requested = int(data["tenantId"])
        elif q.get("tenantId"):
            requested = int(q["tenantId"])
        tid = resolve_tenant_id(user, requested)
        data = data or {}
        b64 = (data.get("imageBase64") or data.get("data") or "").strip()
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        if not b64:
            raise ValidationError("imageBase64 is required")
        content_type = (data.get("contentType") or "image/png").lower()
        ext_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
        }
        ext = ext_map.get(content_type)
        if not ext:
            filename = (data.get("filename") or "logo.png").lower()
            if filename.endswith(".jpg") or filename.endswith(".jpeg"):
                ext = "jpg"
            elif filename.endswith(".webp"):
                ext = "webp"
            else:
                ext = "png"
        try:
            raw = base64.b64decode(b64)
        except Exception as e:
            raise ValidationError(f"Invalid base64 image: {e}")
        if len(raw) > 2 * 1024 * 1024:
            raise ValidationError("Logo must be under 2MB")
        # Basic magic-byte check
        if not (raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:2] == b"\xff\xd8" or raw[:4] == b"RIFF"):
            # allow webp/png/jpeg loosely
            pass

        api_root = Path(__file__).resolve().parents[4]
        media = api_root / "media" / "tenants" / str(tid) / "brand"
        media.mkdir(parents=True, exist_ok=True)
        # Clear other extensions
        for old in media.glob("logo.*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest = media / f"logo.{ext}"
        dest.write_bytes(raw)
        logo_url = f"/media/tenants/{tid}/brand/logo.{ext}"

        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            training = parse_training(t.training_json)
            training.brand_visual.logo_url = logo_url
            t.logo_url = logo_url
            t.training_json = training.model_dump_json()
            _apply_brand_columns(t, training)
            _rebuild_pack(session, t)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=(user or {}).get("userId"),
                action="brand.logo_upload",
                resource_type="tenant",
                resource_id=str(tid),
                detail=logo_url,
            )
            session.commit()
            return create_success_response({"logoUrl": logo_url, "training": training.model_dump()})

    @Delete("/tenants/me/brand/logo")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def delete_logo(self, user=None, query: dict | None = None):
        from pathlib import Path

        q = query or {}
        tid = resolve_tenant_id(user, int(q["tenantId"]) if q.get("tenantId") else None)
        api_root = Path(__file__).resolve().parents[4]
        media = api_root / "media" / "tenants" / str(tid) / "brand"
        for old in media.glob("logo.*"):
            try:
                old.unlink()
            except OSError:
                pass
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            training = parse_training(t.training_json)
            training.brand_visual.logo_url = ""
            t.logo_url = None
            t.training_json = training.model_dump_json()
            _rebuild_pack(session, t)
            session.commit()
            return create_success_response({"logoUrl": None, "deleted": True})

    @Post("/admin/tenants/{tenantId}/brand/logo")
    @RequireModule("tenants")
    @RequirePermission("admin:tenants")
    def admin_upload_logo(self, tenantId: str, data: dict, user=None):
        data = {**(data or {}), "tenantId": int(tenantId)}
        return self.upload_logo(data=data, user=user, query={"tenantId": tenantId})

    @Get("/tenants/me/training/docs")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def list_docs(self, user=None, query: dict | None = None):
        q = query or {}
        tid = resolve_tenant_id(user, int(q["tenantId"]) if q.get("tenantId") else None)
        with get_session() as session:
            docs = session.exec(
                select(TrainingDocument).where(
                    TrainingDocument.tenant_id == tid, TrainingDocument.is_active == True
                )
            ).all()
            return create_success_response(
                [
                    {
                        "documentId": d.document_id,
                        "title": d.title,
                        "category": d.category,
                        "body": d.body,
                        "priority": d.priority,
                    }
                    for d in docs
                ]
            )

    @Post("/tenants/me/training/docs")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def create_doc(self, data: dict, user=None, query: dict | None = None):
        q = query or {}
        requested = None
        if (data or {}).get("tenantId"):
            requested = int(data["tenantId"])
        elif q.get("tenantId"):
            requested = int(q["tenantId"])
        tid = resolve_tenant_id(user, requested)
        title = (data or {}).get("title")
        body = (data or {}).get("body")
        if not title or not body:
            raise ValidationError("title and body required")
        with get_session() as session:
            doc = TrainingDocument(
                tenant_id=tid,
                title=title,
                category=(data or {}).get("category") or "other",
                body=body,
                priority=int((data or {}).get("priority") or 100),
                created_by=(user or {}).get("userId"),
            )
            session.add(doc)
            t = session.get(Tenant, tid)
            if t:
                _rebuild_pack(session, t)
            session.commit()
            session.refresh(doc)
            return create_success_response(
                {"documentId": doc.document_id, "title": doc.title, "category": doc.category},
                201,
            )

    @Delete("/tenants/me/training/docs/{id}")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def delete_doc(self, id: str, user=None, query: dict | None = None):
        q = query or {}
        tid = resolve_tenant_id(user, int(q["tenantId"]) if q.get("tenantId") else None)
        with get_session() as session:
            doc = session.get(TrainingDocument, int(id))
            if not doc or doc.tenant_id != tid:
                raise NotFoundError("Document not found")
            doc.is_active = False
            session.add(doc)
            t = session.get(Tenant, tid)
            if t:
                _rebuild_pack(session, t)
            session.commit()
            return create_success_response({"deleted": True})

    @Post("/invites")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def create_invite(self, data: dict, user=None, query: dict | None = None):
        """Invite a teammate by email. Admin-only."""
        require_user(user)
        q = query or {}
        requested = None
        if (data or {}).get("tenantId") and is_super_admin(user):
            requested = int(data["tenantId"])
        elif q.get("tenantId"):
            requested = int(q["tenantId"])
        tid = resolve_tenant_id(user, requested)
        email = ((data or {}).get("email") or "").strip().lower()
        role = (data or {}).get("role") or "tenant_member"
        with get_session() as session:
            ensure_invite_schema(session)
            tenant = session.get(Tenant, tid)
            if not tenant or not tenant.is_active:
                raise NotFoundError("Tenant not found")
            existing = session.exec(
                select(User).where(User.email == email, User.is_active == True)
            ).first()
            if existing:
                if int(existing.tenant_id or 0) == int(tid):
                    raise ValidationError("User is already a member of this tenant")
                raise AppError(
                    "This email already belongs to another account",
                    409,
                    "EMAIL_IN_USE",
                )
            row, raw = issue_invite_token(
                session,
                tenant_id=tid,
                email=email,
                role=role,
                invited_by=int(user.get("userId") or 0) or None,
            )
            mail = send_tenant_invite_email(
                to_email=email,
                raw_token=raw,
                tenant_name=tenant.name,
                role=row.role,
            )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="tenant.invite.create",
                resource_type="tenant_invite",
                resource_id=str(row.invite_id),
                detail=email,
            )
            session.commit()
            session.refresh(row)
            out = invite_public_dict(row, tenant_name=tenant.name)
            if is_local() and mail.get("devLink"):
                out["devLink"] = mail["devLink"]
            return create_success_response(out, 201)

    @Get("/invites")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def list_invites(self, user=None, query: dict | None = None):
        require_user(user)
        q = query or {}
        tid = resolve_tenant_id(
            user, int(q["tenantId"]) if q.get("tenantId") else None
        )
        with get_session() as session:
            ensure_invite_schema(session)
            now = datetime.utcnow()
            rows = session.exec(
                select(TenantInvite)
                .where(
                    TenantInvite.tenant_id == tid,
                    TenantInvite.status == STATUS_PENDING,
                )
                .order_by(TenantInvite.created_at.desc())
            ).all()
            out = [
                invite_public_dict(row)
                for row in rows
                if row.expires_at and row.expires_at >= now
            ]
            return create_success_response(out)

    @Delete("/invites/{id}")
    @RequireModule("tenants")
    @RequirePermission("tenant:admin", "admin:tenants")
    def revoke_invite(self, id: str, user=None, query: dict | None = None):
        require_user(user)
        q = query or {}
        tid = resolve_tenant_id(
            user, int(q["tenantId"]) if q.get("tenantId") else None
        )
        with get_session() as session:
            ensure_invite_schema(session)
            row = session.get(TenantInvite, int(id))
            if not row or row.tenant_id != tid:
                raise NotFoundError("Invite not found")
            if row.status != STATUS_PENDING:
                raise ValidationError("Only pending invites can be revoked")
            row.status = STATUS_REVOKED
            row.updated_at = datetime.utcnow()
            session.add(row)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user.get("userId"),
                action="tenant.invite.revoke",
                resource_type="tenant_invite",
                resource_id=str(row.invite_id),
            )
            session.commit()
            return create_success_response({"revoked": True, "inviteId": row.invite_id})

    @Post("/invites/{token}/accept")
    @ApiPublic()
    def accept_invite(self, token: str, data: dict | None = None):
        """Accept invite and create membership on the invited tenant."""
        data = data or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or len(username) < 3:
            raise ValidationError("username must be at least 3 characters")
        if not password or len(str(password)) < 8:
            raise ValidationError("password must be at least 8 characters")
        with get_session() as session:
            ensure_invite_schema(session)
            row = load_invite_by_raw_token(session, token)
            assert_invite_acceptable(row)
            tenant = session.get(Tenant, row.tenant_id)
            if not tenant or not tenant.is_active:
                raise AppError("Invalid or expired invite", 400, "INVALID_INVITE")

            existing = session.exec(
                select(User).where(User.email == row.email)
            ).first()
            if existing:
                # Cross-tenant: never move membership via invite
                if int(existing.tenant_id or 0) != int(row.tenant_id):
                    raise AppError(
                        "This email already belongs to another account",
                        409,
                        "EMAIL_IN_USE",
                    )
                raise ValidationError("User is already a member of this tenant")

            if session.exec(select(User).where(User.username == username)).first():
                raise ValidationError("Username already taken")

            role = session.exec(
                select(Role).where(Role.role_name == row.role, Role.is_active == True)
            ).first()
            if not role:
                raise AppError("Invite role is not configured", 500, "SETUP")

            user = User(
                username=username,
                email=row.email,
                password=bcrypt.hash(password),
                role_id=role.role_id,
                tenant_id=row.tenant_id,
                is_active=True,
            )
            session.add(user)
            session.flush()
            row.status = STATUS_ACCEPTED
            row.updated_at = datetime.utcnow()
            session.add(row)
            write_audit(
                session,
                tenant_id=row.tenant_id,
                actor_user_id=user.user_id,
                action="tenant.invite.accept",
                resource_type="tenant_invite",
                resource_id=str(row.invite_id),
                detail=row.email,
            )
            session.commit()
            session.refresh(user)
            return create_success_response(
                {
                    "success": True,
                    "message": "Invite accepted — you can sign in",
                    "user": {
                        "userId": user.user_id,
                        "username": user.username,
                        "email": user.email,
                        "tenantId": user.tenant_id,
                        "roleName": role.role_name,
                    },
                    "tenant": {
                        "tenantId": tenant.tenant_id,
                        "name": tenant.name,
                        "slug": tenant.slug,
                    },
                }
            )
