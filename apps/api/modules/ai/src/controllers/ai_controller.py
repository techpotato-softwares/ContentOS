from __future__ import annotations
import os
from decorators import Controller, Post
from decorators.auth_decorators import RequirePermission, RequireModule
from middleware.error_handler import create_success_response

class AIProvider:
    def chat(self, message: str) -> dict:
        raise NotImplementedError

class StubProvider(AIProvider):
    def chat(self, message: str) -> dict:
        return {"provider": "stub", "reply": f"Echo: {message}"}

class OpenAIProvider(AIProvider):
    def chat(self, message: str) -> dict:
        # Placeholder — wire openai SDK when OPENAI_API_KEY is set
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return StubProvider().chat(message)
        return {"provider": "openai", "reply": f"[openai-stub] {message}", "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini")}

class BedrockProvider(AIProvider):
    def chat(self, message: str) -> dict:
        if not os.environ.get("AWS_REGION"):
            return StubProvider().chat(message)
        return {"provider": "bedrock", "reply": f"[bedrock-stub] {message}", "model": os.environ.get("BEDROCK_MODEL", "anthropic.claude-3-haiku")}

def get_provider() -> AIProvider:
    name = (os.environ.get("AI_PROVIDER") or "stub").lower()
    if name == "openai":
        return OpenAIProvider()
    if name == "bedrock":
        return BedrockProvider()
    return StubProvider()

@Controller(path="/api/ai", lambda_name="ai")
class AiController:
    @Post("/chat")
    @RequireModule("ai")
    @RequirePermission("ai:chat", "admin")
    def chat(self, data: dict, user=None):
        message = (data or {}).get("message") or ""
        result = get_provider().chat(message)
        result["hint"] = "Set AI_PROVIDER=openai|bedrock and provider credentials for live calls."
        return create_success_response(result)
