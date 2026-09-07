from __future__ import annotations

import os

from decorators import Controller, Post
from decorators.auth_decorators import RequirePermission, RequireModule
from database import get_session
from database.models import Tenant
from middleware.error_handler import NotFoundError, ValidationError, create_success_response
from utils.tenant import resolve_tenant_id
from billing.ai_billing import (
    assert_platform_quota,
    meter_ai_success,
    resolve_ai_credentials,
)
from billing.schema import ensure_tenant_billing_schema
from modules.agent.src.providers import get_provider


@Controller(path="/api/ai", lambda_name="ai")
class AiController:
    @Post("/chat")
    @RequireModule("agent")
    @RequirePermission("ai:chat", "agent:chat", "admin")
    def chat(self, data: dict, user=None):
        """Lightweight AI chat with the same hybrid billing metering as agent chat."""
        message = ((data or {}).get("message") or "").strip()
        if not message:
            raise ValidationError("message is required")
        tid = resolve_tenant_id(user)
        ensure_tenant_billing_schema()
        ai_name = ((data or {}).get("aiProvider") or "").strip() or None
        with get_session() as session:
            tenant = session.get(Tenant, tid)
            if not tenant:
                raise NotFoundError("Tenant not found")
            creds = resolve_ai_credentials(tenant, preferred_provider=ai_name)
            assert_platform_quota(tenant, 1)
            provider = get_provider(
                ai_name or creds.provider_hint or os.environ.get("AI_PROVIDER") or "stub",
                api_keys=creds.as_dict(),
            )
            # Prefer rich agent chat when available; stub/simple providers return text
            pack = tenant.context_pack_cached or ""
            if hasattr(provider, "chat"):
                try:
                    reply = provider.chat(message, pack, history=None)
                except TypeError:
                    reply = provider.chat(message)
            else:
                reply = f"Echo: {message}"
            if isinstance(reply, dict):
                text = reply.get("reply") or str(reply)
                provider_label = reply.get("provider")
            else:
                text = str(reply)
                provider_label = ai_name or creds.provider_hint or os.environ.get("AI_PROVIDER") or "stub"
            meter_ai_success(
                session,
                tenant=tenant,
                kind="chat",
                units=1,
                model=getattr(provider, "model", provider_label),
                provider=provider_label,
                creds=creds,
                meta={"route": "/api/ai/chat"},
            )
            session.commit()
            return create_success_response(
                {
                    "provider": provider_label,
                    "reply": text,
                    "billingMode": creds.mode,
                }
            )
