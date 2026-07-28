from __future__ import annotations
import json
from datetime import datetime
from sqlmodel import select
from decorators import Controller, Get, Post, Put, Delete
from decorators.auth_decorators import RequirePermission, RequireModule
from database import get_session
from database.models import Tenant, TrainingDocument
from middleware.error_handler import NotFoundError, ValidationError, create_success_response
from utils.tenant import resolve_tenant_id, is_super_admin, require_user, write_audit
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
