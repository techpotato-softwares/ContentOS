from __future__ import annotations
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


def _brand_lines(tenant: Tenant) -> list[str]:
    t = parse_training(tenant.training_json)
    c, b = t.company, t.brand_visual
    lines = [
        f"Company name text: {c.display_name or c.legal_name}",
        f"Industry: {c.industry}" if c.industry else "",
        f"Website in footer: {c.website}" if c.website else "",
        f"Phone in footer: {c.phone}" if c.phone else "",
        f"Email in footer: {c.email}" if c.email else "",
        f"Primary color: {b.primary_color}" if b.primary_color else "",
        f"Secondary color: {b.secondary_color}" if b.secondary_color else "",
        f"Accent color: {b.accent_color}" if b.accent_color else "",
        f"Visual style: {', '.join(b.visual_style_keywords)}" if b.visual_style_keywords else "",
        f"Do not: {', '.join(b.image_do_nots)}" if b.image_do_nots else "",
    ]
    return [x for x in lines if x]


def _post_dict(p: ContentPost) -> dict:
    return {
        "postId": p.post_id,
        "batchId": p.batch_id,
        "tenantId": p.tenant_id,
        "angle": p.angle,
        "caption": p.caption,
        "imagePrompt": p.image_prompt,
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
        brief = ((data or {}).get("brief") or (data or {}).get("message") or "").strip()
        if not brief:
            raise ValidationError("brief is required")
        news = ((data or {}).get("newsContext") or "").strip()
        if news:
            brief = f"{brief}\n\nINDUSTRY / NEWS CONTEXT TO WEAVE IN:\n{news}"
        tid = resolve_tenant_id(user)
        session_id = (data or {}).get("sessionId")
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            pack = _load_context_pack(session, tenant)
            provider = get_provider()
            plans = provider.plan_variants(brief, pack)
            brand = _brand_lines(tenant)
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
                image_prompt = enrich_image_prompt(plan["image_prompt"], brand)
                img = provider.generate_image(image_prompt)
                uploaded = upload_tenant_image(tid, img)
                post = ContentPost(
                    tenant_id=tid,
                    batch_id=batch.batch_id,
                    user_id=user["userId"],
                    angle=plan["angle"],
                    caption=plan["caption"],
                    image_prompt=image_prompt,
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
                        content=f"Generated {len(posts)} variants (batch #{batch.batch_id}).",
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
