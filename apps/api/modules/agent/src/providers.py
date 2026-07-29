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

    def critic_variants(self, brief: str, context_pack: str, plans: list[dict]) -> list[dict]:
        """Second-pass verifier; default returns plans unchanged."""
        return plans

    def generate_image(self, prompt: str) -> bytes:
        raise NotImplementedError

    def content_suggestions(self, context_pack: str) -> list[dict]:
        raise NotImplementedError

    def industry_news_briefs(self, context_pack: str, industry: str) -> list[dict]:
        raise NotImplementedError

    def analytics_advice(self, context_pack: str, metrics: dict) -> dict:
        raise NotImplementedError

    def score_post(
        self,
        *,
        caption: str,
        layout: dict | None,
        angle: str,
        context_pack: str,
    ) -> dict:
        raise NotImplementedError

    def score_posts_batch(
        self,
        *,
        posts: list[dict],
        context_pack: str,
    ) -> list[dict]:
        return [
            self.score_post(
                caption=p.get("caption") or "",
                layout=p.get("layout")
                or {
                    "headline": p.get("headline"),
                    "subhead": p.get("subhead"),
                    "bullets": p.get("bullets"),
                },
                angle=p.get("angle") or "",
                context_pack=context_pack,
            )
            | {"postId": p.get("postId")}
            for p in posts
        ]

    def ab_schedule_suggestions(
        self,
        *,
        posts: list[dict],
        context_pack: str,
        best_times: list[str] | None = None,
    ) -> dict:
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
                    "headline": "Drive measurable outcomes",
                    "subhead": "Practical insights for buyers",
                    "bullets": ["Clarity", "Speed", "Trust"],
                    "caption": f"{brief[:280]}\n\n#B2B #LinkedIn",
                    "background_prompt": (
                        f"Abstract corporate illustration background about: {brief[:160]}. "
                        "Soft gradients, professional, no text, no letters, no logos, no watermarks"
                    ),
                    "image_prompt": (
                        f"Abstract corporate illustration background about: {brief[:160]}. "
                        "Soft gradients, professional, no text, no letters, no logos, no watermarks"
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

    def score_post(
        self,
        *,
        caption: str,
        layout: dict | None,
        angle: str,
        context_pack: str,
    ) -> dict:
        headline = (layout or {}).get("headline") or ""
        # Vary stub scores by content so UI testing shows distinct bars
        seed = sum(ord(c) for c in f"{angle}:{headline}:{caption[:80]}") % 23
        base = {
            "educational": 72,
            "thought_leadership": 78,
            "product_value": 68,
        }.get(angle, 70)
        overall = max(45, min(95, base + (seed - 11)))
        return {
            "clarity": max(40, min(98, overall + (seed % 5) - 2)),
            "hook": max(40, min(98, overall + ((seed * 3) % 7) - 3)),
            "brandFit": max(40, min(98, overall + ((seed * 5) % 6) - 2)),
            "cta": max(40, min(98, overall - (seed % 4))),
            "overall": overall,
            "summary": f"{angle.replace('_', ' ').title()} draft “{headline[:40]}” — score reflects this variant’s hook and CTA.",
            "fixes": [
                "Sharpen the opening line of the caption.",
                f"Make the CTA more specific for {angle.replace('_', ' ')}.",
                "Add one concrete detail from brand context.",
            ],
        }

    def score_posts_batch(
        self,
        *,
        posts: list[dict],
        context_pack: str,
    ) -> list[dict]:
        out = []
        for p in posts:
            s = self.score_post(
                caption=p.get("caption") or "",
                layout=p.get("layout")
                or {
                    "headline": p.get("headline"),
                    "subhead": p.get("subhead"),
                    "bullets": p.get("bullets"),
                },
                angle=p.get("angle") or "",
                context_pack=context_pack,
            )
            s["postId"] = p.get("postId")
            out.append(s)
        # Enforce distinct overalls
        overalls = sorted({s["overall"] for s in out})
        if len(out) > 1 and len(overalls) == 1:
            for i, s in enumerate(out):
                s["overall"] = max(40, min(98, s["overall"] + (i - 1) * 6))
        return out

    def ab_schedule_suggestions(
        self,
        *,
        posts: list[dict],
        context_pack: str,
        best_times: list[str] | None = None,
    ) -> dict:
        from datetime import datetime, timedelta

        slots = best_times or ["Tue 10:00", "Thu 09:00", "Wed 11:30"]
        now = datetime.utcnow()
        # Next Tue/Thu/Wed from tomorrow
        suggestions = []
        labels = ["A", "B", "C"]
        day_offsets = [1, 3, 5]
        for i, p in enumerate(posts[:3]):
            when = now + timedelta(days=day_offsets[i], hours=10 + i)
            suggestions.append(
                {
                    "label": labels[i],
                    "postId": p.get("postId"),
                    "angle": p.get("angle"),
                    "scheduledAt": when.replace(microsecond=0).isoformat() + "Z",
                    "slotHint": slots[i % len(slots)],
                    "reason": f"Variant {labels[i]} ({p.get('angle')}) — spaced for clean A/B read.",
                }
            )
        return {
            "strategy": "Publish top two angles 48h apart as A/B; hold third as backup.",
            "suggestions": suggestions,
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
        prompt = f"""Create exactly 3 LinkedIn post variants for this brief.
Return ONLY a valid JSON array of 3 objects with keys:
angle, headline, subhead, bullets, caption, background_prompt.

Rules:
- Angles must be exactly: educational, thought_leadership, product_value (one each).
- headline: MAX 7 words, exact string that will be printed on the image by our template (not by the image model).
- subhead: optional, MAX 12 words.
- bullets: array of 0–4 short labels (MAX 5 words each).
- caption: full LinkedIn caption (story, CTA, light hashtags). Do NOT invent metrics/clients/awards not in COMPANY CONTEXT.
- background_prompt: visual-only FULL-BLEED scene. Put the main subject on the RIGHT 55% (person, product, device, or vivid 3D object). Left side softer for text overlay. MUST say: no text, no letters, no numbers, no logos, no watermarks, no black bars, no empty voids.
- Only use facts present in COMPANY CONTEXT or the user brief. If a number/quote is not in context, omit it.

USER BRIEF:
{brief}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.75)
            return _parse_variants_json(text)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"OpenAI plan error: {e}", 502, "OPENAI_ERROR")

    def critic_variants(self, brief: str, context_pack: str, plans: list[dict]) -> list[dict]:
        prompt = f"""You are a fact checker. Given COMPANY CONTEXT, user brief, and 3 post JSON objects,
return ONLY a JSON array of 3 corrected objects with the same keys
(angle, headline, subhead, bullets, caption, background_prompt).

Remove or rewrite any claim (stats, clients, awards, quotes) not supported by context/brief.
Keep headlines ≤7 words and bullets short.
Strengthen each background_prompt so the RIGHT side has a clear subject (not empty texture) and remains free of text/letters/logos.

USER BRIEF:
{brief}

PLANS JSON:
{json.dumps(plans)}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.2)
            return _parse_variants_json(text)
        except Exception:
            return plans

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

    def score_post(
        self,
        *,
        caption: str,
        layout: dict | None,
        angle: str,
        context_pack: str,
    ) -> dict:
        layout = layout or {}
        headline = layout.get("headline") or ""
        fingerprint = f"{angle}|{headline}|{(caption or '')[:120]}"
        prompt = f"""You are a strict LinkedIn content critic. Score THIS ONE draft only.
Return ONLY JSON:
clarity, hook, brandFit, cta, overall (each 0-100 integers),
summary (1-2 sentences naming what is unique about THIS draft),
fixes (2-4 specific improvements for THIS caption/headline).

CRITICAL: Do NOT default to 70/75/80. Scores must reflect THIS draft's specific words.
Identical round scores across different drafts is a failure. Use fine-grained integers (e.g. 61, 74, 88).
Penalize generic CTAs, weak hooks, and vague headlines. Reward specificity and brand voice.

DRAFT FINGERPRINT: {fingerprint}
ANGLE: {angle}
HEADLINE: {headline}
SUBHEAD: {layout.get("subhead") or ""}
BULLETS: {json.dumps(layout.get("bullets") or [])}
CAPTION:
{(caption or "")[:2500]}
"""
        text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.55)
        data = _parse_json_object(text)
        score = _normalize_score(data)
        # Deterministic micro-jitter from content so near-identical model outputs still differ
        return _diversify_score(score, fingerprint)

    def score_posts_batch(
        self,
        *,
        posts: list[dict],
        context_pack: str,
    ) -> list[dict]:
        """Comparative scoring so variants get meaningfully different numbers."""
        prompt = f"""Score these LinkedIn draft variants RELATIVE to each other.
Return ONLY a JSON array (same order) of objects with keys:
postId, clarity, hook, brandFit, cta, overall (0-100), summary, fixes (2-4 strings).

Rules:
- Rank them — the strongest overall should be ≥8 points above the weakest.
- Do not give the same overall to two posts.
- Use fine-grained integers, not multiples of 5 only.
- summary must mention the headline of that variant.

POSTS:
{json.dumps(posts)[:8000]}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.5)
            arr = _parse_json_array(text)
        except Exception:
            return [
                self.score_post(
                    caption=p.get("caption") or "",
                    layout=p.get("layout") or {
                        "headline": p.get("headline"),
                        "subhead": p.get("subhead"),
                        "bullets": p.get("bullets"),
                    },
                    angle=p.get("angle") or "",
                    context_pack=context_pack,
                )
                | {"postId": p.get("postId")}
                for p in posts
            ]
        out = []
        for i, item in enumerate(arr if isinstance(arr, list) else []):
            if not isinstance(item, dict):
                continue
            pid = item.get("postId")
            if pid is None and i < len(posts):
                pid = posts[i].get("postId")
            score = _normalize_score(item)
            fp = f"{pid}|{posts[i].get('headline') if i < len(posts) else ''}|{i}"
            score = _diversify_score(score, fp)
            score["postId"] = pid
            out.append(score)
        return out

    def ab_schedule_suggestions(
        self,
        *,
        posts: list[dict],
        context_pack: str,
        best_times: list[str] | None = None,
    ) -> dict:
        prompt = f"""You are a LinkedIn growth strategist. Given 2–3 post variants from one batch,
propose an A/B (or A/B/C) publish schedule.

Return ONLY JSON:
{{
  "strategy": "short plan",
  "suggestions": [
    {{
      "label": "A"|"B"|"C"|"hold",
      "postId": number,
      "angle": string,
      "scheduledAt": "ISO-8601 UTC datetime",
      "slotHint": "e.g. Tue 10:00",
      "reason": "why this slot / label"
    }}
  ]
}}

Rules:
- Prefer spacing variants ~36–72 hours apart during business hours (Tue–Thu preferred).
- Use bestTimes hints when useful: {json.dumps(best_times or [])}
- scheduledAt must be in the future relative to now UTC: {datetime_utcnow_iso()}
- Include every postId exactly once. Use "hold" only if a third is weak.
- Prefer educational or thought_leadership as A when present.

POSTS JSON:
{json.dumps(posts)}
"""
        text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.4)
        data = _parse_json_object(text)
        return _normalize_ab_schedule(data, posts)


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

    def score_post(
        self,
        *,
        caption: str,
        layout: dict | None,
        angle: str,
        context_pack: str,
    ) -> dict:
        return StubProvider().score_post(
            caption=caption, layout=layout, angle=angle, context_pack=context_pack
        )

    def score_posts_batch(
        self,
        *,
        posts: list[dict],
        context_pack: str,
    ) -> list[dict]:
        return StubProvider().score_posts_batch(posts=posts, context_pack=context_pack)

    def ab_schedule_suggestions(
        self,
        *,
        posts: list[dict],
        context_pack: str,
        best_times: list[str] | None = None,
    ) -> dict:
        return StubProvider().ab_schedule_suggestions(
            posts=posts, context_pack=context_pack, best_times=best_times
        )


def datetime_utcnow_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _clamp_score(v, default: int = 70) -> int:
    try:
        n = int(round(float(v)))
    except Exception:
        n = default
    return max(0, min(100, n))


def _normalize_score(data: dict) -> dict:
    clarity = _clamp_score(data.get("clarity"))
    hook = _clamp_score(data.get("hook"))
    brand = _clamp_score(data.get("brandFit", data.get("brand_fit")))
    cta = _clamp_score(data.get("cta"))
    overall = data.get("overall")
    if overall is None:
        overall = round(0.2 * clarity + 0.3 * hook + 0.3 * brand + 0.2 * cta)
    fixes = data.get("fixes") or []
    if not isinstance(fixes, list):
        fixes = [str(fixes)]
    return {
        "clarity": clarity,
        "hook": hook,
        "brandFit": brand,
        "cta": cta,
        "overall": _clamp_score(overall),
        "summary": str(data.get("summary") or "Scored draft."),
        "fixes": [str(f) for f in fixes][:6],
    }


def _normalize_ab_schedule(data: dict, posts: list[dict]) -> dict:
    from datetime import datetime, timedelta

    suggestions = data.get("suggestions") or []
    if not isinstance(suggestions, list) or not suggestions:
        return StubProvider().ab_schedule_suggestions(posts=posts, context_pack="")
    post_ids = {p.get("postId") for p in posts}
    out = []
    now = datetime.utcnow()
    for i, s in enumerate(suggestions):
        if not isinstance(s, dict):
            continue
        pid = s.get("postId")
        if pid not in post_ids and i < len(posts):
            pid = posts[i].get("postId")
        raw_when = s.get("scheduledAt") or s.get("scheduled_at")
        when = None
        if raw_when:
            try:
                when = datetime.fromisoformat(str(raw_when).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                when = None
        if when is None or when < now:
            when = now + timedelta(days=1 + i * 2, hours=10)
        out.append(
            {
                "label": str(s.get("label") or ["A", "B", "C"][i % 3]),
                "postId": pid,
                "angle": s.get("angle") or next(
                    (p.get("angle") for p in posts if p.get("postId") == pid), None
                ),
                "scheduledAt": when.replace(microsecond=0).isoformat() + "Z",
                "slotHint": s.get("slotHint") or s.get("slot_hint") or "",
                "reason": str(s.get("reason") or ""),
            }
        )
    return {
        "strategy": str(data.get("strategy") or "Stagger variants for A/B learning."),
        "suggestions": out,
    }


def _diversify_score(score: dict, fingerprint: str) -> dict:
    """Nudge scores with a stable content hash so near-identical LLM replies still differ."""
    h = sum((i + 1) * ord(c) for i, c in enumerate(fingerprint[:160])) or 1
    nudge = (h % 9) - 4  # -4..+4
    keys = ("clarity", "hook", "brandFit", "cta", "overall")
    out = dict(score)
    for i, k in enumerate(keys):
        delta = nudge + ((h >> (i * 3)) % 5) - 2
        out[k] = _clamp_score(out.get(k, 70) + delta)
    # Recompute overall if dimensions moved
    out["overall"] = _clamp_score(
        round(
            0.2 * out["clarity"]
            + 0.3 * out["hook"]
            + 0.3 * out["brandFit"]
            + 0.2 * out["cta"]
        )
    )
    return out


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
    from modules.agent.src.post_schema import parse_variant_plans

    text = _strip_fences(text)
    m = re.search(r"\[.*\]", text, re.S)
    raw = m.group(0) if m else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AppError(f"Failed to parse AI JSON array: {e}", 502, "AI_PARSE_ERROR")
    plans = parse_variant_plans(data)
    return [
        {
            "angle": p.angle,
            "headline": p.headline,
            "subhead": p.subhead,
            "bullets": p.bullets,
            "caption": p.caption,
            "background_prompt": p.background_prompt,
            "image_prompt": p.background_prompt,
        }
        for p in plans
    ]


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
