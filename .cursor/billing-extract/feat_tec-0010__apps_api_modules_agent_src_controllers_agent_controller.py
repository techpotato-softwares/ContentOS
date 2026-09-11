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
from modules.agent.src.providers import get_provider, upload_tenant_image, enrich_image_prompt, ANGLES, list_text_providers
from modules.agent.src.post_schema import (
    apply_banned_claims,
    parse_variant_plans,
    LINKEDIN_PRESETS,
    DEFAULT_PRESET,
)
from modules.agent.src.compose import (
    compose_linkedin_post,
    enrich_background_prompt,
    background_looks_empty,
)
from modules.agent.src.image_providers import (
    list_image_models,
    get_image_provider,
    nearest_gen_size,
)
from billing.ai_billing import (
    assert_platform_quota,
    meter_ai_success,
    resolve_ai_credentials,
)
from billing.schema import ensure_tenant_billing_schema


def _ensure_layout_column():
    """Add newer content_posts columns if missing (create_all does not alter)."""
    cols = [
        ("layout_json", "TEXT"),
        ("score_json", "TEXT"),
        ("source_type", "VARCHAR"),
        ("source_ref", "TEXT"),
        ("ab_label", "VARCHAR"),
        ("scheduled_at", "TIMESTAMP"),
    ]
    try:
        from sqlalchemy import text
        from database import get_engine

        with get_engine().begin() as conn:
            for name, typ in cols:
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE content_posts ADD COLUMN IF NOT EXISTS {name} {typ}"
                        )
                    )
                except Exception:
                    try:
                        conn.execute(text(f"ALTER TABLE content_posts ADD COLUMN {name} {typ}"))
                    except Exception:
                        pass
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


def _ensure_chat_session(
    session,
    *,
    tid: int,
    user_id: int,
    session_id,
    title: str,
) -> ChatSession:
    """Return existing chat session or create one (so generate/PDF always land in history)."""
    if session_id:
        cs = session.get(ChatSession, int(session_id))
        if not cs or cs.tenant_id != tid or cs.user_id != user_id:
            raise NotFoundError("Chat session not found")
        return cs
    cs = ChatSession(
        tenant_id=tid,
        user_id=user_id,
        title=(title or "New chat").strip()[:80] or "New chat",
    )
    session.add(cs)
    session.commit()
    session.refresh(cs)
    return cs


def _session_artifacts(session, *, tid: int, session_id: int) -> dict:
    """All generation batches + posts for a chat session (oldest ΓåÆ newest)."""
    batches = session.exec(
        select(GenerationBatch)
        .where(
            GenerationBatch.tenant_id == tid,
            GenerationBatch.session_id == session_id,
        )
        .order_by(GenerationBatch.created_at.asc())
    ).all()
    if not batches:
        return {"batchId": None, "posts": [], "batches": []}

    out_batches = []
    all_posts: list = []
    for b in batches:
        posts = session.exec(
            select(ContentPost)
            .where(
                ContentPost.tenant_id == tid,
                ContentPost.batch_id == b.batch_id,
            )
            .order_by(ContentPost.post_id)
        ).all()
        post_dicts = [_post_dict(p) for p in posts]
        all_posts.extend(post_dicts)
        out_batches.append(
            {
                "batchId": b.batch_id,
                "brief": (b.user_brief or "")[:400],
                "createdAt": b.created_at.isoformat() + "Z" if b.created_at else None,
                "status": b.status,
                "posts": post_dicts,
            }
        )
    latest = batches[-1]
    return {
        "batchId": latest.batch_id,
        "posts": all_posts,
        "batches": out_batches,
    }


def _post_dict(p: ContentPost) -> dict:
    layout = None
    if getattr(p, "layout_json", None):
        try:
            layout = json.loads(p.layout_json)
        except Exception:
            layout = None
    score = None
    if getattr(p, "score_json", None):
        try:
            score = json.loads(p.score_json)
        except Exception:
            score = None
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
        "slides": (layout or {}).get("slides"),
        "hashtags": (layout or {}).get("hashtags"),
        "format": (layout or {}).get("format") or ("text" if not p.image_url else "image"),
        "attachedImage": bool((layout or {}).get("attachedImage") or (
            (layout or {}).get("format") == "text" and p.image_url
        )),
        "score": score,
        "sourceType": getattr(p, "source_type", None),
        "sourceRef": getattr(p, "source_ref", None),
        "abLabel": getattr(p, "ab_label", None),
        "imageUrl": p.image_url,
        "imageS3Key": p.image_s3_key,
        "status": p.status,
        "linkedinPostId": p.linkedin_post_id,
        "scheduledAt": p.scheduled_at.isoformat() + "Z" if getattr(p, "scheduled_at", None) else None,
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
            artifacts = _session_artifacts(session, tid=tid, session_id=cs.session_id)
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
                    "batchId": artifacts["batchId"],
                    "posts": artifacts["posts"],
                    "batches": artifacts["batches"],
                }
            )

    @Get("/image-models")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def image_models(self, user=None):
        default_text = (os_provider())
        providers = list_text_providers()
        # Prefer env default; else first available
        default_id = next((p["id"] for p in providers if p.get("default") and p.get("available")), None)
        if not default_id:
            default_id = next((p["id"] for p in providers if p.get("available")), default_text)
        return create_success_response(
            {
                "models": list_image_models(),
                "presets": [
                    {"id": k, "width": v[0], "height": v[1]} for k, v in LINKEDIN_PRESETS.items()
                ],
                "defaultPreset": DEFAULT_PRESET,
                "defaultRenderMode": "template",
                "textProviders": providers,
                "defaultTextProvider": default_id,
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
        ensure_tenant_billing_schema()
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
            ai_name = ((data or {}).get("aiProvider") or (data or {}).get("textProvider") or "").strip() or None
            creds = resolve_ai_credentials(tenant, preferred_provider=ai_name)
            # Chat meters 1 unit (platform only; BYOK skips consume)
            assert_platform_quota(tenant, 1)
            provider = get_provider(ai_name or creds.provider_hint, api_keys=creds.as_dict())
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
            meter_ai_success(
                session,
                tenant=tenant,
                kind="chat",
                units=1,
                model=getattr(provider, "model", ai_name or "stub"),
                provider=ai_name or creds.provider_hint or creds.source,
                creds=creds,
            )
            session.commit()
            return create_success_response(
                {"sessionId": session_id, "reply": reply, "provider": ai_name or os_provider()}
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
        post_format = (data.get("format") or "image").strip().lower()
        if post_format not in ("text", "image", "carousel"):
            post_format = "image"
        attach_image = bool(data.get("attachImage") or data.get("withImage"))
        # Research text can optionally include a supporting photo
        if post_format == "text" and attach_image:
            pass  # handled in compose branch
        preset = data.get("preset") or DEFAULT_PRESET
        if preset not in LINKEDIN_PRESETS:
            preset = DEFAULT_PRESET
        width, height = LINKEDIN_PRESETS[preset]
        # Carousel slides work better as square
        if post_format == "carousel":
            width, height = LINKEDIN_PRESETS.get("linkedin_square", (1080, 1080))
        render_mode = (data.get("renderMode") or "template").strip().lower()
        if render_mode not in ("template", "native_text"):
            render_mode = "template"
        image_model = data.get("imageModel")
        ai_name = (data.get("aiProvider") or data.get("textProvider") or "").strip() or None
        tid = resolve_tenant_id(user)
        session_id = data.get("sessionId")
        source_type = (data.get("sourceType") or "brief").strip()
        source_ref = (data.get("sourceRef") or "").strip() or None
        user_note = (data.get("userNote") or "").strip()  # e.g. "Repurpose PDF: file.pdf"
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")

            ensure_tenant_billing_schema()
            # Always attach to a chat session so history + variants reload together
            title_seed = user_note or source_ref or brief
            cs = _ensure_chat_session(
                session,
                tid=tid,
                user_id=user["userId"],
                session_id=session_id,
                title=title_seed[:60],
            )
            session_id = cs.session_id

            training = parse_training(tenant.training_json)
            length_pref = training.messaging.linkedin_post_length_preference or "medium"
            pack = _load_context_pack(session, tenant)
            expected_units = max(1, min(int(data.get("variantCount") or 3), 8))
            creds = resolve_ai_credentials(tenant, preferred_provider=ai_name)
            assert_platform_quota(tenant, expected_units)
            provider = get_provider(ai_name or creds.provider_hint, api_keys=creds.as_dict())
            raw_plans = provider.plan_variants(brief, pack, format=post_format)
            raw_plans = provider.critic_variants(brief, pack, raw_plans, format=post_format)
            plans = parse_variant_plans(
                raw_plans, format=post_format, brief=brief, length_pref=length_pref
            )
            banned = training.messaging.banned_claims or []
            plans = [apply_banned_claims(p, banned) for p in plans]

            brand = _brand_dict(tenant)
            brand_lines = _brand_lines(tenant)
            img_provider = None
            gen_size = None
            if post_format in ("image", "carousel") or (post_format == "text" and attach_image):
                img_provider = get_image_provider(image_model, api_keys=creds.as_dict())
                gen_size = nearest_gen_size(
                    width, height, getattr(img_provider, "model_id", "gpt-image-1")
                )

            batch = GenerationBatch(
                tenant_id=tid,
                user_id=user["userId"],
                session_id=int(session_id),
                user_brief=brief,
                status="completed",
            )
            session.add(batch)
            session.commit()
            session.refresh(batch)

            posts = []
            for plan in plans:
                layout = plan.to_layout_dict()
                uploaded = {"s3Key": None, "imageUrl": None}
                bg_prompt = plan.background_prompt or ""

                if post_format == "text":
                    layout["format"] = "text"
                    layout["postStyle"] = "research"
                    if plan.hashtags:
                        layout["hashtags"] = plan.hashtags
                    uploaded = {"s3Key": None, "imageUrl": None}
                    bg_prompt = ""
                    if attach_image and img_provider and gen_size:
                        bg_prompt = enrich_background_prompt(
                            plan.background_prompt
                            or f"Editorial supporting photo about {plan.headline}, no text",
                            brand,
                        )
                        # Supporting photo only ΓÇö no text overlay template
                        bg = img_provider.generate_background(bg_prompt, gen_size)
                        try:
                            from PIL import Image
                            import io

                            im = Image.open(io.BytesIO(bg)).convert("RGB")
                            im = im.resize((width, height), Image.Resampling.LANCZOS)
                            buf = io.BytesIO()
                            im.save(buf, format="PNG")
                            final_bytes = buf.getvalue()
                        except Exception:
                            final_bytes = bg
                        uploaded = upload_tenant_image(tid, final_bytes)
                        layout["attachedImage"] = True
                    post = ContentPost(
                        tenant_id=tid,
                        batch_id=batch.batch_id,
                        user_id=user["userId"],
                        angle=plan.angle,
                        caption=plan.caption,
                        image_prompt=bg_prompt,
                        layout_json=json.dumps(layout),
                        image_s3_key=uploaded.get("s3Key"),
                        image_url=uploaded.get("imageUrl"),
                        status="draft",
                        source_type=source_type,
                        source_ref=source_ref,
                    )
                elif post_format == "carousel":
                    slide_layouts = []
                    cover_url = None
                    for slide in plan.slides[:8]:
                        slide_layout = {
                            "angle": plan.angle,
                            "headline": slide.headline,
                            "subhead": (slide.body or "")[:120],
                            "bullets": [],
                            "caption": plan.caption,
                            "background_prompt": slide.visual_prompt or plan.background_prompt,
                        }
                        s_bg = enrich_background_prompt(
                            slide.visual_prompt or "Clean corporate gradient, no text",
                            brand,
                        )
                        bg = img_provider.generate_background(s_bg, gen_size)
                        if background_looks_empty(bg):
                            bg = img_provider.generate_background(
                                s_bg + "\nFill with a clear subject on the right. No empty void.",
                                gen_size,
                            )
                        slide_bytes = compose_linkedin_post(
                            bg,
                            slide_layout,
                            width=width,
                            height=height,
                            brand=brand,
                            tenant_id=tid,
                        )
                        s_up = upload_tenant_image(tid, slide_bytes)
                        slide_layouts.append(
                            {
                                "headline": slide.headline,
                                "body": slide.body,
                                "visual_prompt": slide.visual_prompt,
                                "imageUrl": s_up["imageUrl"],
                            }
                        )
                        if not cover_url:
                            cover_url = s_up["imageUrl"]
                            uploaded = s_up
                    layout = {
                        "format": "carousel",
                        "angle": plan.angle,
                        "headline": plan.headline,
                        "subhead": plan.subhead,
                        "bullets": plan.bullets,
                        "caption": plan.caption,
                        "slides": slide_layouts,
                    }
                    post = ContentPost(
                        tenant_id=tid,
                        batch_id=batch.batch_id,
                        user_id=user["userId"],
                        angle=plan.angle,
                        caption=plan.caption,
                        image_prompt=bg_prompt,
                        layout_json=json.dumps(layout),
                        image_s3_key=uploaded.get("s3Key"),
                        image_url=cover_url,
                        status="draft",
                        source_type=source_type,
                        source_ref=source_ref,
                    )
                else:
                    bg_prompt = enrich_background_prompt(plan.background_prompt, brand)
                    if render_mode == "native_text":
                        native_prompt = enrich_image_prompt(
                            (
                                f"LinkedIn graphic. Headline text exactly: '{plan.headline}'. "
                                f"Subhead: '{plan.subhead}'. Bullets: {', '.join(plan.bullets)}. "
                                f"{bg_prompt}"
                            ),
                            brand_lines,
                        )
                        img = img_provider.generate_background(native_prompt, gen_size)
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
                        if background_looks_empty(bg):
                            retry_prompt = (
                                bg_prompt
                                + "\nRETRY: Previous frame was empty. Fill the RIGHT half with a clear "
                                "photoreal subject (person using technology OR premium product shot). "
                                "No blank parchment, no black void."
                            )
                            bg = img_provider.generate_background(retry_prompt, gen_size)
                        final_bytes = compose_linkedin_post(
                            bg,
                            layout,
                            width=width,
                            height=height,
                            brand=brand,
                            tenant_id=tid,
                        )

                    uploaded = upload_tenant_image(tid, final_bytes)
                    layout["format"] = "image"
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
                        source_type=source_type,
                        source_ref=source_ref,
                    )
                session.add(post)
                posts.append(post)

            # Persist chat history for this generation (PDF/URL always; brief when new session)
            history_user = user_note
            if not history_user:
                if source_type == "url" and source_ref:
                    history_user = f"Repurpose: {source_ref}"
                elif source_type == "pdf" and source_ref:
                    history_user = f"Repurpose PDF: {source_ref}"

            prior = session.exec(
                select(ChatMessage).where(ChatMessage.session_id == int(session_id))
            ).all()
            # For brief generate into an empty/new session, store the brief as the user turn
            if not history_user and not prior:
                history_user = brief[:500]

            if history_user:
                session.add(
                    ChatMessage(
                        session_id=int(session_id),
                        tenant_id=tid,
                        role="user",
                        content=history_user,
                    )
                )
            src_label = {
                "url": "from URL",
                "pdf": "from PDF",
            }.get(source_type, "")
            session.add(
                ChatMessage(
                    session_id=int(session_id),
                    tenant_id=tid,
                    role="assistant",
                    content=(
                        f"Generated {len(posts)} {post_format} "
                        f"{'post' if len(posts) == 1 else 'variants'} {src_label} "
                        f"(batch #{batch.batch_id}, {render_mode}/{preset})."
                    ).strip(),
                )
            )
            cs.updated_at = datetime.utcnow()
            if (not cs.title or cs.title == "New chat") and history_user:
                cs.title = history_user[:60]
            session.add(cs)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="agent.generate",
                resource_type="generation_batch",
                resource_id=str(batch.batch_id),
                detail=json.dumps({"brief": brief[:400], "format": post_format}),
            )
            meter_ai_success(
                session,
                tenant=tenant,
                kind="generate_batch",
                units=len(posts),
                model=getattr(provider, "model", ai_name or "stub"),
                provider=ai_name or creds.provider_hint or os_provider(),
                creds=creds,
                meta={
                    "batchId": batch.batch_id,
                    "format": post_format,
                    "sessionId": session_id,
                },
            )
            session.commit()
            for p in posts:
                session.refresh(p)
            return create_success_response(
                {
                    "batchId": batch.batch_id,
                    "sessionId": session_id,
                    "posts": [_post_dict(p) for p in posts],
                    "angles": list(ANGLES),
                    "preset": preset,
                    "format": post_format,
                    "attachImage": attach_image if post_format == "text" else False,
                    "renderMode": render_mode,
                    "imageModel": getattr(img_provider, "model_id", image_model)
                    if img_provider
                    else None,
                    "sourceType": source_type,
                    "aiProvider": ai_name or os_provider(),
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

    @Post("/posts/{id}/score")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review")
    def score_post(self, id: str, user=None):
        _ensure_layout_column()
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            post = session.get(ContentPost, int(id))
            if not tenant or not post or post.tenant_id != tid:
                raise NotFoundError("Post not found")
            layout = None
            if post.layout_json:
                try:
                    layout = json.loads(post.layout_json)
                except Exception:
                    layout = None
            pack = _load_context_pack(session, tenant)
            score = get_provider().score_post(
                caption=post.caption or "",
                layout=layout,
                angle=post.angle or "",
                context_pack=pack,
            )
            post.score_json = json.dumps(score)
            post.updated_at = datetime.utcnow()
            session.add(post)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="agent.score_post",
                resource_type="content_post",
                resource_id=str(post.post_id),
                detail=str(score.get("overall")),
            )
            session.commit()
            session.refresh(post)
            return create_success_response(_post_dict(post))

    @Post("/batches/{id}/score")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review")
    def score_batch(self, id: str, user=None):
        """Comparative AI scores for all variants in a batch (distinct overalls)."""
        _ensure_layout_column()
        tid = resolve_tenant_id(user)
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            batch = session.get(GenerationBatch, int(id))
            if not tenant or not batch or batch.tenant_id != tid:
                raise NotFoundError("Batch not found")
            posts = session.exec(
                select(ContentPost).where(
                    ContentPost.batch_id == batch.batch_id,
                    ContentPost.tenant_id == tid,
                )
            ).all()
            if not posts:
                raise ValidationError("No posts in batch")
            pack = _load_context_pack(session, tenant)
            payload = [_post_dict(p) for p in posts]
            scores = get_provider().score_posts_batch(posts=payload, context_pack=pack)
            by_id = {s.get("postId"): s for s in scores if isinstance(s, dict)}
            updated = []
            for p in posts:
                score = by_id.get(p.post_id)
                if not score:
                    continue
                # strip postId before persist
                clean = {k: v for k, v in score.items() if k != "postId"}
                p.score_json = json.dumps(clean)
                p.updated_at = datetime.utcnow()
                session.add(p)
                updated.append(p)
            write_audit(
                session,
                tenant_id=tid,
                actor_user_id=user["userId"],
                action="agent.score_batch",
                resource_type="generation_batch",
                resource_id=str(batch.batch_id),
            )
            session.commit()
            for p in updated:
                session.refresh(p)
            return create_success_response(
                {"batchId": batch.batch_id, "posts": [_post_dict(p) for p in posts]}
            )

    @Post("/repurpose")
    @RequireModule("agent")
    @RequirePermission("agent:chat")
    def repurpose(self, data: dict, user=None):
        """Extract text from URL or PDF and optionally generate 3 variants."""
        _ensure_layout_column()
        data = data or {}
        url = (data.get("url") or "").strip()
        pdf_b64 = data.get("pdfBase64") or data.get("pdf_base64")
        filename = data.get("filename") or "upload.pdf"
        # Default extract-only so clients can stage attachments; pass generate:true to run now
        generate_now = bool(data.get("generate", False))

        from modules.agent.src.extract import extract_from_url, extract_from_pdf_base64

        if url:
            extracted = extract_from_url(url)
        elif pdf_b64:
            extracted = extract_from_pdf_base64(str(pdf_b64), filename=filename)
        else:
            raise ValidationError("Provide url or pdfBase64")

        if not generate_now:
            return create_success_response({"extracted": extracted, "posts": []})

        # Persist under chat history (create session if needed via generate)
        user_context = (data.get("userContext") or data.get("message") or "").strip()
        user_note = (
            f"Repurpose: {extracted['sourceRef']}"
            if extracted["sourceType"] == "url"
            else f"Repurpose PDF: {extracted.get('title') or filename}"
        )
        if user_context:
            user_note = f"{user_note}\n\n{user_context}"
        brief = extracted["brief"]
        if user_context:
            brief = f"{user_context}\n\nSOURCE MATERIAL:\n{extracted['brief']}"
        gen_payload = {
            "brief": brief,
            "sessionId": data.get("sessionId"),
            "preset": data.get("preset"),
            "format": data.get("format") or "image",
            "attachImage": bool(data.get("attachImage") or data.get("withImage")),
            "renderMode": data.get("renderMode"),
            "imageModel": data.get("imageModel"),
            "aiProvider": data.get("aiProvider") or data.get("textProvider"),
            "sourceType": extracted["sourceType"],
            "sourceRef": extracted["sourceRef"],
            "userNote": user_note,
        }
        result = self.generate(gen_payload, user=user)
        # generate returns API response dict ΓÇö unwrap data if wrapped
        body = result
        if isinstance(result, dict) and "body" in result:
            try:
                body = json.loads(result["body"])
            except Exception:
                body = result
        payload = body.get("data") if isinstance(body, dict) and "data" in body else body
        if isinstance(payload, dict):
            payload = {**payload, "extracted": extracted}
            return create_success_response(payload, 201)
        return result

    @Post("/batches/{id}/ab-schedule")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review")
    def ab_schedule(self, id: str, data: dict | None = None, user=None):
        """Suggest A/B schedule slots for a generation batch; optionally apply."""
        _ensure_layout_column()
        tid = resolve_tenant_id(user)
        apply = bool((data or {}).get("apply"))
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            batch = session.get(GenerationBatch, int(id))
            if not tenant or not batch or batch.tenant_id != tid:
                raise NotFoundError("Batch not found")
            posts = session.exec(
                select(ContentPost).where(
                    ContentPost.batch_id == batch.batch_id,
                    ContentPost.tenant_id == tid,
                )
            ).all()
            if len(posts) < 2:
                raise ValidationError("Need at least 2 variants in the batch for A/B")
            pack = _load_context_pack(session, tenant)
            advice = get_provider().analytics_advice(pack, PLACEHOLDER_METRICS)
            best_times = advice.get("bestTimes") if isinstance(advice, dict) else None
            plan = get_provider().ab_schedule_suggestions(
                posts=[_post_dict(p) for p in posts],
                context_pack=pack,
                best_times=best_times if isinstance(best_times, list) else None,
            )
            applied = []
            if apply:
                by_id = {p.post_id: p for p in posts}
                for s in plan.get("suggestions") or []:
                    post = by_id.get(s.get("postId"))
                    if not post:
                        continue
                    raw = s.get("scheduledAt")
                    when = None
                    if raw:
                        try:
                            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(
                                tzinfo=None
                            )
                        except Exception:
                            when = None
                    post.scheduled_at = when
                    post.ab_label = str(s.get("label") or "")[:16] or None
                    post.updated_at = datetime.utcnow()
                    session.add(post)
                    applied.append(_post_dict(post))
                write_audit(
                    session,
                    tenant_id=tid,
                    actor_user_id=user["userId"],
                    action="agent.ab_schedule_apply",
                    resource_type="generation_batch",
                    resource_id=str(batch.batch_id),
                    detail=plan.get("strategy"),
                )
                session.commit()
                for p in posts:
                    session.refresh(p)
                applied = [_post_dict(p) for p in posts]
            else:
                session.commit()
            return create_success_response(
                {
                    "batchId": batch.batch_id,
                    "strategy": plan.get("strategy"),
                    "suggestions": plan.get("suggestions") or [],
                    "applied": apply,
                    "posts": applied if apply else [_post_dict(p) for p in posts],
                }
            )

    @Get("/insights/weekly-snapshot")
    @RequireModule("agent")
    @RequirePermission("agent:chat", "posts:review", "tenant:admin")
    def weekly_snapshot_preview(self, user=None):
        """Preview this week's team performance stats (no email)."""
        from modules.agent.src.weekly_snapshot import collect_tenant_stats, _week_window

        tid = resolve_tenant_id(user)
        start, end = _week_window()
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            stats = collect_tenant_stats(session, tid, start, end)
            return create_success_response(
                {"tenantId": tid, "tenantName": tenant.name, "stats": stats}
            )

    @Post("/insights/weekly-snapshot/send")
    @RequireModule("agent")
    @RequirePermission("tenant:admin", "admin:tenants")
    def weekly_snapshot_send(self, data: dict | None = None, user=None):
        """Send weekly snapshot email now (Amazon SES) for current tenant."""
        from modules.agent.src.weekly_snapshot import send_weekly_snapshots

        tid = resolve_tenant_id(user)
        # Super admin may pass tenantId to send for another / all
        target = (data or {}).get("tenantId")
        if target == "all" and "admin:tenants" in (user.get("permissions") or []):
            result = send_weekly_snapshots()
        else:
            result = send_weekly_snapshots(tenant_id=int(target) if target else tid)
        return create_success_response(result)


def os_provider() -> str:
    import os

    return (os.environ.get("AI_PROVIDER") or "openai").lower()
