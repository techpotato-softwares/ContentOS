from __future__ import annotations
import json
from datetime import datetime
from sqlmodel import select
from decorators import Controller, Get, Post
from decorators.auth_decorators import RequirePermission, RequireModule
from database import get_session
from database.models import Tenant, ChatSession, ChatMessage, GenerationBatch, ContentPost, TrainingDocument
from middleware.error_handler import NotFoundError, ValidationError, create_success_response
from utils.tenant import resolve_tenant_id, write_audit
from training.schema import parse_training, render_context_pack, DocumentRef
from modules.agent.src.providers import get_provider, upload_tenant_image, enrich_image_prompt, ANGLES
from modules.agent.src.post_schema import (
    apply_banned_claims,
    parse_variant_plans,
    LINKEDIN_PRESETS,
    DEFAULT_PRESET,
)
from modules.agent.src.compose import compose_linkedin_post
from modules.agent.src.image_providers import (
    list_image_models,
    get_image_provider,
    nearest_gen_size,
)


def _ensure_layout_column():
    """Add layout_json if missing (create_all does not alter existing tables)."""
    try:
        from sqlalchemy import text
        from database import get_engine

        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE content_posts ADD COLUMN IF NOT EXISTS layout_json TEXT"
                )
            )
    except Exception:
        try:
            from sqlalchemy import text
            from database import get_engine

            with get_engine().begin() as conn:
                conn.execute(text("ALTER TABLE content_posts ADD COLUMN layout_json TEXT"))
        except Exception:
            pass


def _load_context_pack(session, tenant: Tenant) -> str:
    if tenant.context_pack_cached:
        return tenant.context_pack_cached
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
    session.add(tenant)
    return pack


def _brand_dict(tenant: Tenant) -> dict:
    t = parse_training(tenant.training_json)
    c, b = t.company, t.brand_visual
    return {
        "display_name": c.display_name or c.legal_name or tenant.app_display_name or tenant.name,
        "company_name": c.display_name or c.legal_name,
        "website": c.website,
        "phone": c.phone,
        "email": c.email,
        "primary_color": b.primary_color or tenant.primary_color or "#0d9488",
        "secondary_color": b.secondary_color or tenant.secondary_color or "#134e4a",
        "accent_color": b.accent_color or tenant.accent_color or "#2dd4bf",
        "logo_url": b.logo_url or tenant.logo_url,
        "visual_style_keywords": b.visual_style_keywords,
        "image_do_nots": b.image_do_nots,
    }


def _brand_lines(tenant: Tenant) -> list[str]:
    d = _brand_dict(tenant)
    lines = [
        f"Company name text: {d['display_name']}",
        f"Website in footer: {d['website']}" if d.get("website") else "",
        f"Phone in footer: {d['phone']}" if d.get("phone") else "",
        f"Email in footer: {d['email']}" if d.get("email") else "",
        f"Primary color: {d['primary_color']}",
        f"Secondary color: {d['secondary_color']}",
        f"Accent color: {d['accent_color']}",
    ]
    return [x for x in lines if x]


def _post_dict(p: ContentPost) -> dict:
    layout = None
    if getattr(p, "layout_json", None):
        try:
            layout = json.loads(p.layout_json)
        except Exception:
            layout = None
    return {
        "postId": p.post_id,
        "batchId": p.batch_id,
        "tenantId": p.tenant_id,
        "angle": p.angle,
        "caption": p.caption,
        "imagePrompt": p.image_prompt,
        "layout": layout,
        "headline": (layout or {}).get("headline"),
        "subhead": (layout or {}).get("subhead"),
        "bullets": (layout or {}).get("bullets"),
        "imageUrl": p.image_url,
        "imageS3Key": p.image_s3_key,
        "status": p.status,
        "linkedinPostId": p.linkedin_post_id,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
    }


PLACEHOLDER_METRICS = {
    "followers": 1280,
    "impressions28d": 18400,
    "engagementRate": 3.2,
    "topPostType": "image",
    "avgReach": 920,
    "note": "Placeholder until LinkedIn Analytics API is connected",
}


@Controller(path="/api/agent", lambda_name="agent")
class AgentController:
    @Post("/sessions")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def create_session(self, data: dict, user=None):
        tid = resolve_tenant_id(user)
        title = (data or {}).get("title") or "New chat"
        with get_session() as session:
            s = ChatSession(tenant_id=tid, user_id=user["userId"], title=title)
            session.add(s)
            session.commit()
            session.refresh(s)
            return create_success_response(
                {"sessionId": s.session_id, "title": s.title}, 201
            )

    @Get("/sessions")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def list_sessions(self, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            rows = session.exec(
                select(ChatSession)
                .where(ChatSession.tenant_id == tid, ChatSession.user_id == user["userId"])
                .order_by(ChatSession.updated_at.desc())
            ).all()
            return create_success_response(
                [
                    {
                        "sessionId": s.session_id,
                        "title": s.title,
                        "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
                    }
                    for s in rows
                ]
            )

    @Get("/sessions/{sessionId}/messages")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def get_messages(self, sessionId: str, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            cs = session.get(ChatSession, int(sessionId))
            if not cs or cs.tenant_id != tid or cs.user_id != user["userId"]:
                raise NotFoundError("Chat session not found")
            rows = session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == cs.session_id, ChatMessage.tenant_id == tid)
                .order_by(ChatMessage.created_at)
            ).all()
            return create_success_response(
                {
                    "sessionId": cs.session_id,
                    "title": cs.title,
                    "messages": [
                        {
                            "messageId": m.message_id,
                            "role": m.role,
                            "content": m.content,
                            "createdAt": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in rows
                    ],
                }
            )

    @Get("/image-models")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def image_models(self, user=None):
        return create_success_response(
            {
                "models": list_image_models(),
                "presets": [
                    {"id": k, "width": v[0], "height": v[1]} for k, v in LINKEDIN_PRESETS.items()
                ],
                "defaultPreset": DEFAULT_PRESET,
                "defaultRenderMode": "template",
            }
        )

    @Post("/chat")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def chat(self, data: dict, user=None):
        message = ((data or {}).get("message") or "").strip()
        if not message:
            raise ValidationError("message is required")
        tid = resolve_tenant_id(user)
        session_id = (data or {}).get("sessionId")
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            if not session_id:
                cs = ChatSession(tenant_id=tid, user_id=user["userId"], title=message[:60])
                session.add(cs)
                session.commit()
                session.refresh(cs)
                session_id = cs.session_id
            else:
                cs = session.get(ChatSession, int(session_id))
                if not cs or cs.tenant_id != tid:
                    raise NotFoundError("Chat session not found")

            session.add(
                ChatMessage(
                    session_id=session_id,
                    tenant_id=tid,
                    role="user",
                    content=message,
                )
            )
            history_rows = session.exec(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            ).all()
            history = [{"role": m.role, "content": m.content} for m in history_rows if m.role in ("user", "assistant")]
            pack = _load_context_pack(session, tenant)
            provider = get_provider()
            reply = provider.chat(message, pack, history)
            session.add(
                ChatMessage(
                    session_id=session_id,
                    tenant_id=tid,
                    role="assistant",
                    content=reply,
                )
            )
            cs.updated_at = datetime.utcnow()
            session.add(cs)
            session.commit()
            return create_success_response(
                {"sessionId": session_id, "reply": reply, "provider": (os_provider())}
            )

    @Post("/generate")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def generate(self, data: dict, user=None):
        _ensure_layout_column()
        data = data or {}
        brief = (data.get("brief") or data.get("message") or "").strip()
        if not brief:
            raise ValidationError("brief is required")
        news = (data.get("newsContext") or "").strip()
        if news:
            brief = f"{brief}\n\nINDUSTRY / NEWS CONTEXT TO WEAVE IN:\n{news}"
        preset = data.get("preset") or DEFAULT_PRESET
        if preset not in LINKEDIN_PRESETS:
            preset = DEFAULT_PRESET
        width, height = LINKEDIN_PRESETS[preset]
        render_mode = (data.get("renderMode") or "template").strip().lower()
        if render_mode not in ("template", "native_text"):
            render_mode = "template"
        image_model = data.get("imageModel")
        tid = resolve_tenant_id(user)
        session_id = data.get("sessionId")
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            training = parse_training(tenant.training_json)
            pack = _load_context_pack(session, tenant)
            provider = get_provider()
            raw_plans = provider.plan_variants(brief, pack)
            raw_plans = provider.critic_variants(brief, pack, raw_plans)
            plans = parse_variant_plans(raw_plans)
            banned = training.messaging.banned_claims or []
            plans = [apply_banned_claims(p, banned) for p in plans]

            brand = _brand_dict(tenant)
            brand_lines = _brand_lines(tenant)
            img_provider = get_image_provider(image_model)
            gen_size = nearest_gen_size(width, height, getattr(img_provider, "model_id", "gpt-image-1"))

            batch = GenerationBatch(
                tenant_id=tid,
                user_id=user["userId"],
                session_id=int(session_id) if session_id else None,
                user_brief=brief,
                status="completed",
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)

            posts = []
            for plan in plans:
                layout = plan.to_layout_dict()
                bg_prompt = plan.background_prompt
                if render_mode == "native_text":
                    # Experimental: ask model to render text (spelling not guaranteed)
                    native_prompt = enrich_image_prompt(
                        (
                            f"LinkedIn graphic. Headline text exactly: '{plan.headline}'. "
                            f"Subhead: '{plan.subhead}'. Bullets: {', '.join(plan.bullets)}. "
                            f"{bg_prompt}"
                        ),
                        brand_lines,
                    )
                    img = img_provider.generate_background(native_prompt, gen_size)
                    # Still resize via compose without replacing text if possible — use raw
                    try:
                        from PIL import Image
                        import io

                        im = Image.open(io.BytesIO(img)).convert("RGB")
                        im = im.resize((width, height), Image.Resampling.LANCZOS)
                        buf = io.BytesIO()
                        im.save(buf, format="PNG")
                        final_bytes = buf.getvalue()
                    except Exception:
                        final_bytes = img
                else:
                    bg = img_provider.generate_background(bg_prompt, gen_size)
                    final_bytes = compose_linkedin_post(
                        bg,
                        layout,
                        width=width,
                        height=height,
                        brand=brand,
                        tenant_id=tid,
                    )

                uploaded = upload_tenant_image(tid, final_bytes)
                post = ContentPost(
                    tenant_id=tid,
                    batch_id=batch.batch_id,
                    user_id=user["userId"],
                    angle=plan.angle,
                    caption=plan.caption,
                    image_prompt=bg_prompt,
                    layout_json=json.dumps(layout),
                    image_s3_key=uploaded["s3Key"],
                    image_url=uploaded["imageUrl"],
                    status="draft",
                )
                session.add(post)
                posts.append(post)
            if session_id:
                session.add(
                    ChatMessage(
                        session_id=int(session_id),
                        tenant_id=tid,
                        role="assistant",
                        content=f"Generated {len(posts)} variants (batch #{batch.batch_id}, {render_mode}/{preset}).",
                    )
                )
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="agent.generate",
                resource_type="generation_batch",
                resource_id=str(batch.batch_id),
                detail=brief[:500],
            )
            session.commit()
            for p in posts:
                session.refresh(p)
            return create_success_response(
                {
                    "batchId": batch.batch_id,
                    "posts": [_post_dict(p) for p in posts],
                    "angles": list(ANGLES),
                    "preset": preset,
                    "renderMode": render_mode,
                    "imageModel": getattr(img_provider, "model_id", image_model),
                },
                201,
            )

    @Get("/batches/{id}")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review")
    def get_batch(self, id: str, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            batch = session.get(GenerationBatch, int(id))
            if not batch or batch.tenant_id != tid:
                raise NotFoundError("Batch not found")
            posts = session.exec(
                select(ContentPost).where(
                    ContentPost.batch_id == batch.batch_id, ContentPost.tenant_id == tid
                )
            ).all()
            return create_success_response(
                {
                    "batchId": batch.batch_id,
                    "brief": batch.user_brief,
                    "posts": [_post_dict(p) for p in posts],
                }
            )

    @Get("/insights/suggestions")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def insights_suggestions(self, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            pack = _load_context_pack(session, tenant)
            session.commit()
            ideas = get_provider().content_suggestions(pack)
            return create_success_response({"suggestions": ideas})

    @Get("/insights/news")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def insights_news(self, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            training = parse_training(tenant.training_json)
            pack = _load_context_pack(session, tenant)
            session.commit()
            items = get_provider().industry_news_briefs(pack, training.company.industry)
            return create_success_response(
                {
                    "industry": training.company.industry,
                    "items": items,
                    "mode": "ai_briefings",
                }
            )

    @Get("/insights/analytics")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review")
    def insights_analytics(self, user=None):
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            pack = _load_context_pack(session, tenant)
            session.commit()
            advice = get_provider().analytics_advice(pack, PLACEHOLDER_METRICS)
            advice["placeholder"] = True
            return create_success_response(advice)


def os_provider() -> str:
    import os

    return (os.environ.get("AI_PROVIDER") or "openai").lower()
