"""AI providers for chat + LinkedIn image post generation."""
from __future__ import annotations
import base64
import json
import os
import re
import uuid
from pathlib import Path
import httpx
from utils.logger import logger
from utils.tenant import tenant_s3_prefix
from utils.s3 import get_s3_config
from middleware.error_handler import AppError


SYSTEM_STANCE = """You are ContentOS, a B2B LinkedIn content assistant for a company tenant.
Use COMPANY CONTEXT for brand voice, colors, and known facts so posts stay consistent.
Fulfill the user's request even if the topic is not listed in context.
Do not invent false company metrics, clients, or awards; stay generic or ask briefly if needed — still help generate.
"""

IMAGE_LAYOUT_SPEC = """
LinkedIn image creative — CRITICAL layout & typography rules:
- Canvas: landscape 16:9 / ~1.91:1 (LinkedIn feed). Full composition must fit inside the frame.
- Safe margins: keep ALL text at least 8% inward from every edge. Never clip, crop, or cut off letters.
- Headline: MAX 5–7 words, huge bold sans-serif, high contrast, fully visible on one or two lines.
- Subline: MAX 12 words OR omit. Never long paragraphs inside the image.
- Feature bullets: at most 4 short labels (2–4 words each), large icons, generous spacing.
- Footer contact bar: one thin strip; website/phone/email only if they fit fully — otherwise omit.
- Company name: short readable text (not a fake logo mark).
- No tiny text, no dense paragraphs, no watermark-style microcopy, no overflowing boxes.
- Prefer fewer words + stronger illustration over cramming copy.
- Apply brand primary/secondary/accent colors from COMPANY CONTEXT.
- Flat or soft 3D corporate illustration; polished B2B LinkedIn style.
"""

TEXT_SAFETY_APPENDIX = """
Final checks before rendering:
1) Every word of the headline is complete and inside the safe area.
2) No text touches or crosses image borders.
3) Landscape composition — not a square poster stretched later.
4) Large readable type; if copy won't fit, shorten it — never shrink until illegible.
"""

ANGLES = ("educational", "thought_leadership", "product_value")

# Local media root (served by FastAPI at /media)
API_ROOT = Path(__file__).resolve().parents[3]
MEDIA_ROOT = API_ROOT / "media"


class AIProvider:
    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        raise NotImplementedError

    def plan_variants(self, brief: str, context_pack: str) -> list[dict]:
        raise NotImplementedError

    def generate_image(self, prompt: str) -> bytes:
        raise NotImplementedError

    def content_suggestions(self, context_pack: str) -> list[dict]:
        raise NotImplementedError

    def industry_news_briefs(self, context_pack: str, industry: str) -> list[dict]:
        raise NotImplementedError

    def analytics_advice(self, context_pack: str, metrics: dict) -> dict:
        raise NotImplementedError


class StubProvider(AIProvider):
    """Explicit stub only — never used when AI_PROVIDER=openai."""

    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        return (
            f"I'll help craft LinkedIn image posts for that. "
            f"(stub) You asked: {message[:200]}. "
            "Say 'generate' to create 3 variants."
        )

    def plan_variants(self, brief: str, context_pack: str) -> list[dict]:
        out = []
        for angle in ANGLES:
            out.append(
                {
                    "angle": angle,
                    "caption": f"{brief[:280]}\n\n#B2B #LinkedIn",
                    "image_prompt": (
                        f"Landscape LinkedIn graphic 1536x1024, {angle.replace('_', ' ')} style, "
                        f"short 5-word headline fully inside safe margins, large type, "
                        f"illustration about: {brief[:160]}, no cut-off text, no tiny text"
                    ),
                }
            )
        return out

    def generate_image(self, prompt: str) -> bytes:
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )

    def content_suggestions(self, context_pack: str) -> list[dict]:
        return [
            {
                "title": "Product value post",
                "angle": "product_value",
                "brief": "Create an informative LinkedIn image post highlighting our core product benefits for ICP buyers.",
                "why": "Maps offerings to buyer pain points.",
            },
            {
                "title": "Educational tip",
                "angle": "educational",
                "brief": "Share a practical industry tip as a branded LinkedIn carousel-style graphic.",
                "why": "Builds authority without a hard sell.",
            },
            {
                "title": "Thought leadership",
                "angle": "thought_leadership",
                "brief": "Comment on a current industry trend and how buyers should respond.",
                "why": "Supports follower growth via timely takes.",
            },
        ]

    def industry_news_briefs(self, context_pack: str, industry: str) -> list[dict]:
        return [
            {
                "headline": f"Key shifts in {industry or 'your industry'}",
                "summary": "Buyers are prioritizing automation, compliance, and measurable ROI.",
                "suggestedBrief": f"Create a LinkedIn informative post on how {industry or 'our industry'} is changing and what leaders should do next.",
                "sourceNote": "AI briefing (not a live news feed)",
            }
        ]

    def analytics_advice(self, context_pack: str, metrics: dict) -> dict:
        return {
            "summary": "Placeholder analytics — connect LinkedIn Analytics for live data.",
            "bestTimes": ["Tue 10:00", "Wed 11:30", "Thu 09:00"],
            "suggestedTopics": ["Educational how-to", "Customer outcome story", "Industry trend take"],
            "recommendations": [
                "Post 3–4 times per week with one educational and one product-value graphic.",
                "Use image posts with clear headlines; they typically outperform text-only.",
            ],
            "metrics": metrics,
        }


class OpenAIProvider(AIProvider):
    def __init__(self):
        self.api_key = (os.environ.get("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.image_model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        if not self.api_key:
            raise AppError(
                "OPENAI_API_KEY is missing. Set it in apps/api/.env and restart the API.",
                500,
                "AI_CONFIG",
            )

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _chat_json(self, system: str, user: str, temperature: float = 0.7) -> str:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                },
            )
            if r.status_code >= 400:
                raise AppError(
                    f"OpenAI failed ({r.status_code}): {r.text[:400]}",
                    502,
                    "OPENAI_ERROR",
                )
            return r.json()["choices"][0]["message"]["content"]

    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_STANCE + "\n\n" + context_pack},
        ]
        for h in (history or [])[-12:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=self._headers(),
                    json={"model": self.model, "messages": messages, "temperature": 0.7},
                )
                if r.status_code >= 400:
                    raise AppError(
                        f"OpenAI chat failed ({r.status_code}): {r.text[:400]}",
                        502,
                        "OPENAI_ERROR",
                    )
                return r.json()["choices"][0]["message"]["content"]
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"OpenAI chat error: {e}", 502, "OPENAI_ERROR")

    def plan_variants(self, brief: str, context_pack: str) -> list[dict]:
        prompt = f"""Create exactly 3 LinkedIn image-post variants for this brief.
Return ONLY valid JSON array of 3 objects with keys: angle, caption, image_prompt.
Angles must be exactly: educational, thought_leadership, product_value (one each).
Captions: professional LinkedIn style for the request (full story lives in the caption), sparingly use hashtags. Do NOT prefix with [Educational] labels.
image_prompt: detailed prompt for a landscape LinkedIn INFORMATIONAL graphic.
CRITICAL: Put only SHORT on-image text — specify the exact headline words (≤7 words) and any bullet labels (≤4 words each).
Long explanations belong in caption, NOT in the image. Never ask for sentences that could get cut off.
{IMAGE_LAYOUT_SPEC}
{TEXT_SAFETY_APPENDIX}
Apply brand colors and company display name; include website/phone/email in footer only if short enough to fit fully.

USER BRIEF:
{brief}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.8)
            return _parse_variants_json(text)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"OpenAI plan error: {e}", 502, "OPENAI_ERROR")

    def generate_image(self, prompt: str) -> bytes:
        """Call OpenAI Images API. Prefer landscape LinkedIn sizes; accept url or b64_json."""
        # LinkedIn feed is landscape — default 1536x1024 for gpt-image-*; avoid square crops.
        size = (os.environ.get("OPENAI_IMAGE_SIZE") or "1536x1024").strip()
        model = self.image_model
        gpt_sizes = ("1024x1024", "1536x1024", "1024x1536", "auto")
        if model.startswith("gpt-image") and size not in gpt_sizes:
            size = "1536x1024"
        if model.startswith("dall-e-3") and size not in ("1024x1024", "1792x1024", "1024x1792"):
            size = "1792x1024"

        payload: dict = {
            "model": model,
            "prompt": prompt[:3900],
            "n": 1,
            "size": size,
        }

        try:
            with httpx.Client(timeout=180.0) as client:
                r = client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=self._headers(),
                    json=payload,
                )
                # Prefer landscape fallbacks before square
                if r.status_code >= 400:
                    for fallback in ("1536x1024", "1792x1024", "1024x1024"):
                        if fallback == payload.get("size"):
                            continue
                        if model.startswith("gpt-image") and fallback not in gpt_sizes:
                            continue
                        payload["size"] = fallback
                        r = client.post(
                            "https://api.openai.com/v1/images/generations",
                            headers=self._headers(),
                            json=payload,
                        )
                        if r.status_code < 400:
                            break
                if r.status_code >= 400:
                    raise AppError(
                        f"OpenAI image failed ({r.status_code}): {r.text[:500]}",
                        502,
                        "OPENAI_IMAGE_ERROR",
                    )
                data = r.json()["data"][0]
                b64 = data.get("b64_json")
                if b64:
                    return base64.b64decode(b64)
                url = data.get("url")
                if url:
                    img = client.get(url, timeout=120.0)
                    img.raise_for_status()
                    return img.content
                raise AppError(
                    "OpenAI image response missing b64_json/url",
                    502,
                    "OPENAI_IMAGE_ERROR",
                )
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"OpenAI image error: {e}", 502, "OPENAI_IMAGE_ERROR")

    def content_suggestions(self, context_pack: str) -> list[dict]:
        prompt = """Based on COMPANY CONTEXT, return ONLY a JSON array of 6 LinkedIn content ideas.
Each object keys: title, angle (educational|thought_leadership|product_value|celebration|industry_news), brief, why.
brief must be a ready-to-use generation prompt for an informative branded LinkedIn image post.
Focus on domain the company works in so the team does not need extra research."""
        text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.75)
        return _parse_json_array(text)

    def industry_news_briefs(self, context_pack: str, industry: str) -> list[dict]:
        prompt = f"""For industry "{industry or 'B2B technology'}", return ONLY a JSON array of 5 industry news/topic briefs.
Each object keys: headline, summary, suggestedBrief, sourceNote.
suggestedBrief = ready prompt to generate a LinkedIn informative image+caption post using this topic as context.
sourceNote should say these are AI industry briefings for ideation (not scraped headlines), unless citing a well-known public theme.
Keep summaries practical for B2B LinkedIn marketers."""
        text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.6)
        return _parse_json_array(text)

    def analytics_advice(self, context_pack: str, metrics: dict) -> dict:
        prompt = f"""Given placeholder LinkedIn metrics JSON and company context, return ONLY a JSON object with keys:
summary (string), bestTimes (string array), suggestedTopics (string array), recommendations (string array of actionable tips).
Metrics: {json.dumps(metrics)}
Recommend what to publish and when for reach/followers."""
        text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.5)
        data = _parse_json_object(text)
        data["metrics"] = metrics
        return data


class BedrockProvider(AIProvider):
    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        try:
            import boto3

            client = boto3.client(
                "bedrock-runtime",
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
            )
            model = os.environ.get("BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": SYSTEM_STANCE + "\n\n" + context_pack,
                "messages": [{"role": "user", "content": message}],
            }
            resp = client.invoke_model(modelId=model, body=json.dumps(body))
            payload = json.loads(resp["body"].read())
            return payload["content"][0]["text"]
        except Exception as e:
            raise AppError(f"Bedrock chat failed: {e}", 502, "BEDROCK_ERROR")

    def plan_variants(self, brief: str, context_pack: str) -> list[dict]:
        text = self.chat(
            f"Return ONLY JSON array of 3 objects angle/caption/image_prompt for LinkedIn posts. Brief: {brief}",
            context_pack,
        )
        return _parse_variants_json(text)

    def generate_image(self, prompt: str) -> bytes:
        raise AppError(
            "Bedrock image generation is not configured. Set AI_PROVIDER=openai for images.",
            501,
            "NOT_IMPLEMENTED",
        )

    def content_suggestions(self, context_pack: str) -> list[dict]:
        return StubProvider().content_suggestions(context_pack)

    def industry_news_briefs(self, context_pack: str, industry: str) -> list[dict]:
        return StubProvider().industry_news_briefs(context_pack, industry)

    def analytics_advice(self, context_pack: str, metrics: dict) -> dict:
        return StubProvider().analytics_advice(context_pack, metrics)


def enrich_image_prompt(prompt: str, brand_lines: list[str]) -> str:
    extra = "\n".join(f"- {line}" for line in brand_lines if line)
    return (
        f"{prompt.strip()}\n\nBrand constraints:\n{extra}\n"
        f"{IMAGE_LAYOUT_SPEC}\n{TEXT_SAFETY_APPENDIX}"
    ).strip()


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_variants_json(text: str) -> list[dict]:
    data = _parse_json_array(text)
    out = []
    for i, item in enumerate(data[:3]):
        if not isinstance(item, dict):
            continue
        angle = item.get("angle") or ANGLES[min(i, len(ANGLES) - 1)]
        out.append(
            {
                "angle": angle,
                "caption": item.get("caption") or "",
                "image_prompt": item.get("image_prompt") or item.get("imagePrompt") or "",
            }
        )
    if len(out) < 3:
        raise AppError(f"AI returned {len(out)} variants, need 3", 502, "AI_PARSE_ERROR")
    return out[:3]


def _parse_json_array(text: str) -> list:
    text = _strip_fences(text)
    m = re.search(r"\[.*\]", text, re.S)
    raw = m.group(0) if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AppError(f"Failed to parse AI JSON array: {e}", 502, "AI_PARSE_ERROR")
    if not isinstance(data, list):
        raise AppError("AI returned non-array JSON", 502, "AI_PARSE_ERROR")
    return data


def _parse_json_object(text: str) -> dict:
    text = _strip_fences(text)
    m = re.search(r"\{.*\}", text, re.S)
    raw = m.group(0) if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AppError(f"Failed to parse AI JSON object: {e}", 502, "AI_PARSE_ERROR")
    if not isinstance(data, dict):
        raise AppError("AI returned non-object JSON", 502, "AI_PARSE_ERROR")
    return data


def get_provider() -> AIProvider:
    name = (os.environ.get("AI_PROVIDER") or "openai").lower().strip()
    key_present = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    logger.info(
        "AI provider resolve",
        {"provider": name, "openai_key_present": key_present},
    )
    if name == "stub":
        return StubProvider()
    if name == "bedrock":
        return BedrockProvider()
    if name == "openai":
        return OpenAIProvider()
    raise AppError(
        f"Unknown AI_PROVIDER={name}. Use openai | bedrock | stub.",
        500,
        "AI_CONFIG",
    )


def upload_tenant_image(tenant_id: int, image_bytes: bytes, suffix: str = "png") -> dict[str, str]:
    """Upload to S3, or save under apps/api/media for local IS_LOCAL."""
    conf = get_s3_config()
    key = f"{tenant_s3_prefix(tenant_id)}/{uuid.uuid4().hex}.{suffix}"
    is_local = os.environ.get("IS_LOCAL") == "true"
    if is_local and not os.environ.get("FORCE_S3"):
        dest = MEDIA_ROOT / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes)
        # Same-origin path so Vite /media proxy works for view + download
        return {"s3Key": key, "imageUrl": f"/media/{key}"}
    import boto3

    client = boto3.client("s3", region_name=conf.region)
    client.put_object(
        Bucket=conf.bucket_name,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    url = f"https://{conf.bucket_name}.s3.{conf.region}.amazonaws.com/{key}"
    return {"s3Key": key, "imageUrl": url}
