from __future__ import annotations
import json
from datetime import datetime
from sqlmodel import select
from decorators import Controller, Get, Post, Put, Delete
from decorators.auth_decorators import RequirePermission, RequireModule
from database import get_session
from database.models import Tenant, TrainingDocument
from middleware.error_handler import AppError, NotFoundError, ValidationError, create_success_response
from utils.tenant import resolve_tenant_id, is_super_admin, require_user, write_audit
from utils.ai_billing import ai_settings_public, assert_byok_allowed
from utils.ai_secrets import merge_tenant_ai_secrets, peek_tenant_ai_key_flags
from utils.tenant_billing_schema import ensure_tenant_billing_columns
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

    @Get("/tenants/me/ai-settings")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "tenant:admin", "admin:tenants")
    def get_ai_settings(self, user=None):
        """Hybrid AI billing settings for the caller's tenant only (no raw keys)."""
        require_user(user)
        ensure_tenant_billing_columns()
        tid = resolve_tenant_id(user)
        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")
            return create_success_response(ai_settings_public(t))

    @Put("/tenants/me/ai-settings")
    @RequireModule("tenants")
    @RequirePermission("training:manage", "admin:tenants")
    def put_ai_settings(self, data: dict, user=None):
        """Update billing mode and BYOK keys for the caller's tenant.

        Plan tier is not editable here (Stripe/Razorpay checkout owns upgrades).
        Super-admin cannot change another tenant's plan via this endpoint.
        """
        require_user(user)
        ensure_tenant_billing_columns()
        data = data or {}
        # Reject cross-tenant / plan edits on this route
        if data.get("tenantId") is not None or data.get("planTier") is not None or data.get("plan") is not None:
            raise ValidationError(
                "Plan changes are not allowed on AI settings. Use billing checkout to upgrade."
            )

        tid = resolve_tenant_id(user)
        mode_raw = data.get("aiBillingMode")
        openai_key = data.get("openaiApiKey")
        gemini_key = data.get("geminiApiKey")
        clear_openai = bool(data.get("clearOpenai"))
        clear_gemini = bool(data.get("clearGemini"))

        with get_session() as session:
            t = session.get(Tenant, tid)
            if not t:
                raise NotFoundError("Tenant not found")

            target_mode = (t.ai_billing_mode or "platform").strip().lower()
            if mode_raw is not None:
                target_mode = str(mode_raw).strip().lower()
                if target_mode not in ("platform", "byok"):
                    raise ValidationError("aiBillingMode must be 'platform' or 'byok'")

            key_touch = (
                clear_openai
                or clear_gemini
                or (isinstance(openai_key, str) and openai_key.strip())
                or (isinstance(gemini_key, str) and gemini_key.strip())
            )

            if target_mode == "byok" or key_touch:
                assert_byok_allowed(t)

            # Preview resulting key flags before writing secrets
            preview_flags = peek_tenant_ai_key_flags(tid, t.ai_secret_arn)
            if clear_openai:
                preview_flags["openaiConfigured"] = False
            elif isinstance(openai_key, str) and openai_key.strip():
                preview_flags["openaiConfigured"] = True
            if clear_gemini:
                preview_flags["geminiConfigured"] = False
            elif isinstance(gemini_key, str) and gemini_key.strip():
                preview_flags["geminiConfigured"] = True

            if target_mode == "byok" and not (
                preview_flags["openaiConfigured"] or preview_flags["geminiConfigured"]
            ):
                raise AppError(
                    "BYOK mode requires at least one configured AI key.",
                    400,
                    "BYOK_KEYS_MISSING",
                )

            if key_touch:
                # Empty strings are ignored (not clears); use clearOpenai/clearGemini flags
                new_arn = merge_tenant_ai_secrets(
                    tid,
                    t.ai_secret_arn,
                    openai_api_key=openai_key if isinstance(openai_key, str) and openai_key.strip() else None,
                    gemini_api_key=gemini_key if isinstance(gemini_key, str) and gemini_key.strip() else None,
                    clear_openai=clear_openai,
                    clear_gemini=clear_gemini,
                )
                t.ai_secret_arn = new_arn

            if mode_raw is not None:
                t.ai_billing_mode = target_mode

            t.updated_at = datetime.utcnow()
            session.add(t)
            flags_final = peek_tenant_ai_key_flags(tid, t.ai_secret_arn)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=(user or {}).get("userId"),
                action="ai_settings.update",
                resource_type="tenant",
                resource_id=str(tid),
                detail=json.dumps(
                    {
                        "aiBillingMode": t.ai_billing_mode,
                        "openaiConfigured": flags_final["openaiConfigured"],
                        "geminiConfigured": flags_final["geminiConfigured"],
                        "clearedOpenai": clear_openai,
                        "clearedGemini": clear_gemini,
                        "keysUpdated": bool(key_touch),
                    }
                ),
            )
            session.commit()
            session.refresh(t)
            return create_success_response(ai_settings_public(t))

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
