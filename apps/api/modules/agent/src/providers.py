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


SYSTEM_STANCE = """You are ContentOS, a LinkedIn content assistant for a company tenant.
Use COMPANY CONTEXT for brand voice, colors, and known facts so posts stay consistent.
Fulfill the USER BRIEF topic fully — every variant must stay centered on that topic.
Do not invent false company metrics, clients, or awards. If a fact is missing, omit it or use non-numeric framing — never invent numbers. Do NOT replace the brief topic with a generic company promo.
"""

CAPTION_LENGTH_RANGES = {
    "short": (80, 120),
    "medium": (150, 220),
    "long": (220, 320),
}


def caption_length_rule(preference: str | None = None) -> str:
    pref = (preference or "medium").strip().lower()
    if pref not in CAPTION_LENGTH_RANGES:
        pref = "medium"
    lo, hi = CAPTION_LENGTH_RANGES[pref]
    return (
        f"Caption length preference '{pref}': write {lo}–{hi} words "
        f"(never fewer than {lo} words)."
    )


def _length_pref_from_pack(context_pack: str) -> str:
    m = re.search(r"Length:\s*(\w+)", context_pack or "", re.I)
    if m:
        return m.group(1).strip().lower()
    return "medium"


TOPIC_LOCK_RULES = """
TOPIC LOCK (mandatory for every variant):
- The USER BRIEF topic is the subject of ALL variants. Do not pivot to an unrelated product pitch.
- Name or clearly reference the brief topic in the first 2 lines of every caption.
- Angles are lenses on the SAME topic:
  - educational = teach something concrete about this topic
  - thought_leadership = opinion / point of view on this topic
  - product_value = how this topic creates value for the reader (brand only as a supporting lens, not a replacement topic)
- Prefer brief-specific details before brand CTAs.
"""

RESEARCH_TEXT_RULES = """
RESEARCH / NATIVE TEXT POST structure (LinkedIn feed — text-first, not an image graphic):
1) Hook (1–2 short lines) — curiosity or sharp claim about the USER BRIEF topic.
2) Context (2–4 lines) — why this matters now for the ICP.
3) Research / insight body — 3–5 short paragraphs OR numbered takeaways grounded in the brief + COMPANY CONTEXT.
   Use line breaks liberally (LinkedIn scannability). Prefer concrete mechanisms over buzzwords.
4) Practical takeaway — one clear action the reader can take this week.
5) Soft CTA — invite comments / experiences (not a hard sales pitch).
6) Hashtags — end with 3–6 relevant hashtags on their own lines or a final line
   (mix of niche + 1–2 broader tags). Example shape: #TopicKeyword #Industry #B2B
- Do NOT invent studies, % metrics, client names, or awards not in COMPANY CONTEXT / brief.
- If research depth is thin, say what is known qualitatively — never fabricate citations.
- Caption is the FULL post body (this is what gets published to LinkedIn).
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

    def plan_variants(
        self, brief: str, context_pack: str, *, format: str = "image"
    ) -> list[dict]:
        raise NotImplementedError

    def critic_variants(
        self, brief: str, context_pack: str, plans: list[dict], *, format: str = "image"
    ) -> list[dict]:
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

    def plan_variants(
        self, brief: str, context_pack: str, *, format: str = "image"
    ) -> list[dict]:
        topic = (brief or "this topic").strip()
        fmt = (format or "image").strip().lower()
        if fmt == "carousel":
            slides = []
            for i in range(6):
                slides.append(
                    {
                        "headline": f"Slide {i + 1}: {topic[:40]}",
                        "body": f"Key point {i + 1} about {topic[:80]}.",
                        "visual_prompt": (
                            f"Clean LinkedIn carousel slide about {topic[:100]}, "
                            "no text in image, professional"
                        ),
                    }
                )
            caption = (
                f"{topic}\n\nHere is a practical breakdown of what matters and what to do next. "
                "We walk through the problem, the insight, proof points, and a clear next step "
                "for teams who want results without the fluff. Save this carousel and share it "
                "with a teammate who owns this area.\n\n#LinkedIn #Learning"
            )
            return [
                {
                    "angle": "educational",
                    "headline": topic[:60] or "Carousel insight",
                    "subhead": "A practical narrative",
                    "bullets": [],
                    "caption": caption,
                    "background_prompt": "",
                    "slides": slides,
                    "format": "carousel",
                }
            ]
        out = []
        for angle in ANGLES:
            tag = "".join(w.capitalize() for w in topic.split()[:3] if w.isalpha()) or "Insight"
            caption = (
                f"{topic}\n\n"
                f"Most teams talk about this — few dig into what actually moves the needle.\n\n"
                f"Here's an {angle.replace('_', ' ')} research take:\n\n"
                f"1) The real constraint is rarely the tool — it's the operating rhythm around {topic[:60]}.\n"
                f"2) Leaders who win treat this as a system: diagnose → pilot → measure → scale.\n"
                f"3) The practical move this week: pick one bottleneck tied to this topic and run a 7-day experiment.\n\n"
                f"What are you seeing in your world? Drop a comment — specific stories help everyone learn faster.\n\n"
                f"#{tag} #LinkedIn #B2B #Leadership #Growth"
            )
            item = {
                "angle": angle,
                "headline": (topic[:50] or "Drive better outcomes")[:60],
                "subhead": "Research-style LinkedIn text post",
                "bullets": ["Hook", "Insight", "Action"],
                "caption": caption,
                "background_prompt": (
                    f"Abstract corporate illustration about: {topic[:160]}. "
                    "Soft gradients, professional, no text, no letters, no logos, no watermarks"
                ),
                "image_prompt": (
                    f"Abstract corporate illustration about: {topic[:160]}. "
                    "Soft gradients, professional, no text, no letters, no logos, no watermarks"
                ),
                "format": fmt,
                "hashtags": [f"#{tag}", "#LinkedIn", "#B2B", "#Leadership", "#Growth"],
            }
            if fmt == "text":
                item["background_prompt"] = (
                    f"Editorial LinkedIn supporting photo vibe about {topic[:100]}, "
                    "cinematic, no text, no letters, no logos"
                )
                item["image_prompt"] = item["background_prompt"]
            out.append(item)
        return out if fmt != "carousel" else out[:1]

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

    def plan_variants(
        self, brief: str, context_pack: str, *, format: str = "image"
    ) -> list[dict]:
        fmt = (format or "image").strip().lower()
        if fmt not in ("text", "image", "carousel"):
            fmt = "image"
        length_rule = caption_length_rule(_length_pref_from_pack(context_pack))

        if fmt == "carousel":
            prompt = f"""Create ONE LinkedIn carousel post plan for this brief.
Return ONLY a valid JSON array with exactly 1 object with keys:
angle, headline, subhead, bullets, caption, slides.
slides must be an array of 5–8 objects with keys: headline, body, visual_prompt.

Rules:
{TOPIC_LOCK_RULES}
- angle: educational (narrative arc on the SAME topic: hook → insight → proof → CTA).
- caption: full LinkedIn caption for the carousel. {length_rule}
- Each slide headline: MAX 7 words; body: 1–2 short sentences on the brief topic.
- visual_prompt: background-only scene, no text/letters/logos.
- Only use facts present in COMPANY CONTEXT or the user brief.

USER BRIEF:
{brief}
"""
        elif fmt == "text":
            prompt = f"""Create exactly 3 LinkedIn RESEARCH / native TEXT posts for this brief.
These are feed posts meant to be published as text (optionally with a supporting photo later) — NOT image-graphic creatives.

Return ONLY a valid JSON array of 3 objects with keys:
angle, headline, subhead, bullets, caption, hashtags, background_prompt.

Rules:
{TOPIC_LOCK_RULES}
{RESEARCH_TEXT_RULES}
- Angles must be exactly: educational, thought_leadership, product_value (one each) — lenses on the SAME topic.
- headline: short hook (MAX 12 words) — usually mirrors the first line of the caption.
- subhead: optional 1-line thesis.
- bullets: 3–5 short research takeaways (MAX 12 words each) that ALSO appear expanded in the caption.
- caption: full publishable LinkedIn post following RESEARCH / NATIVE TEXT POST structure. {length_rule}
- hashtags: array of 3–6 strings (include the #). Also append them at the end of caption.
- background_prompt: optional supporting photo scene (no text/letters/logos) if a visual is attached later — still required as a string.
- Only use facts from COMPANY CONTEXT or the user brief.

USER BRIEF:
{brief}
"""
        else:
            prompt = f"""Create exactly 3 LinkedIn post variants for this brief.
Return ONLY a valid JSON array of 3 objects with keys:
angle, headline, subhead, bullets, caption, background_prompt.

Rules:
{TOPIC_LOCK_RULES}
- Angles must be exactly: educational, thought_leadership, product_value (one each) — lenses on the SAME topic.
- headline: MAX 7 words, exact string that will be printed on the image by our template (not by the image model).
- subhead: optional, MAX 12 words.
- bullets: array of 0–4 short labels (MAX 5 words each).
- caption: full LinkedIn caption (story, CTA, light hashtags). {length_rule}
- background_prompt: visual-only FULL-BLEED scene. Put the main subject on the RIGHT 55% (person, product, device, or vivid 3D object). Left side softer for text overlay. MUST say: no text, no letters, no numbers, no logos, no watermarks, no black bars, no empty voids.
- Only use facts present in COMPANY CONTEXT or the user brief. If a number/quote is not in context, omit it.

USER BRIEF:
{brief}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.75)
            plans = _parse_variants_json(text)
            for p in plans:
                if isinstance(p, dict):
                    p["format"] = fmt
            return plans
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"OpenAI plan error: {e}", 502, "OPENAI_ERROR")

    def critic_variants(
        self, brief: str, context_pack: str, plans: list[dict], *, format: str = "image"
    ) -> list[dict]:
        fmt = (format or "image").strip().lower()
        length_rule = caption_length_rule(_length_pref_from_pack(context_pack))
        keys = (
            "angle, headline, subhead, bullets, caption, slides"
            if fmt == "carousel"
            else (
                "angle, headline, subhead, bullets, caption, hashtags, background_prompt"
                if fmt == "text"
                else "angle, headline, subhead, bullets, caption, background_prompt"
            )
        )
        n = 1 if fmt == "carousel" else 3
        prompt = f"""You are a fact checker and topic guardian. Given COMPANY CONTEXT, user brief, and {n} post JSON object(s),
return ONLY a JSON array of {n} corrected object(s) with keys: {keys}.

Rules:
{TOPIC_LOCK_RULES}
{"- Preserve RESEARCH / NATIVE TEXT POST structure (hook → insight → takeaway → CTA → hashtags)." if fmt == "text" else ""}
{"- Ensure 3–6 hashtags remain at the end of caption; do not invent fake studies or metrics." if fmt == "text" else ""}
- Remove or rewrite any claim (stats, clients, awards, quotes) not supported by context/brief.
- Do NOT dilute the brief topic when removing unsupported claims; expand with on-topic explanation instead of generic B2B filler.
- Keep captions on-topic and satisfy: {length_rule}
- Keep headlines ≤7 words (≤12 for text format) and bullets short.
{"- Strengthen each background_prompt so the RIGHT side has a clear subject (not empty texture) and remains free of text/letters/logos." if fmt == "image" else ""}
{"- Keep supporting background_prompt free of text/letters/logos (used if a photo is attached to the text post)." if fmt == "text" else ""}
{"- Keep 5–8 slides; each slide must advance the same topic narrative." if fmt == "carousel" else ""}

USER BRIEF:
{brief}

PLANS JSON:
{json.dumps(plans)}
"""
        try:
            text = self._chat_json(SYSTEM_STANCE + "\n\n" + context_pack, prompt, temperature=0.2)
            out = _parse_variants_json(text)
            for p in out:
                if isinstance(p, dict):
                    p["format"] = fmt
            return out
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


class GeminiProvider(OpenAIProvider):
    """Google Gemini for text/planning. Images stay on OpenAI via image_providers."""

    def __init__(self):
        self.api_key = (os.environ.get("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
        self.model = (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()
        # Kept for OpenAIProvider.generate_image fallback if ever called
        self.image_model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        if not self.api_key:
            raise AppError(
                "GEMINI_API_KEY is missing. Set it in apps/api/.env and restart the API.",
                500,
                "AI_CONFIG",
            )

    def _gemini_url(self) -> str:
        model = self.model
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={self.api_key}"
        )

    def _extract_gemini_text(self, data: dict) -> str:
        try:
            parts = data["candidates"][0]["content"]["parts"]
            texts = [p.get("text") or "" for p in parts if isinstance(p, dict)]
            out = "\n".join(t for t in texts if t).strip()
            if out:
                return out
        except Exception:
            pass
        raise AppError(
            f"Gemini returned empty/unreadable content: {str(data)[:300]}",
            502,
            "GEMINI_ERROR",
        )

    def _chat_json(self, system: str, user: str, temperature: float = 0.7) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json",
            },
        }
        try:
            with httpx.Client(timeout=90.0) as client:
                r = client.post(self._gemini_url(), json=payload)
                if r.status_code >= 400:
                    raise AppError(
                        f"Gemini failed ({r.status_code}): {r.text[:400]}",
                        502,
                        "GEMINI_ERROR",
                    )
                return self._extract_gemini_text(r.json())
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Gemini error: {e}", 502, "GEMINI_ERROR")

    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        contents = []
        for h in (history or [])[-12:]:
            role = h.get("role") or "user"
            # Gemini uses "model" for assistant turns
            g_role = "model" if role == "assistant" else "user"
            contents.append({"role": g_role, "parts": [{"text": h.get("content") or ""}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_STANCE + "\n\n" + context_pack}]
            },
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(self._gemini_url(), json=payload)
                if r.status_code >= 400:
                    raise AppError(
                        f"Gemini chat failed ({r.status_code}): {r.text[:400]}",
                        502,
                        "GEMINI_ERROR",
                    )
                return self._extract_gemini_text(r.json())
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Gemini chat error: {e}", 502, "GEMINI_ERROR")

    def generate_image(self, prompt: str) -> bytes:
        # Main compose path uses image_providers (OpenAI). Keep explicit message if called.
        if (os.environ.get("OPENAI_API_KEY") or "").strip():
            return OpenAIProvider.generate_image(OpenAIProvider(), prompt)
        raise AppError(
            "Gemini handles text only. Set OPENAI_API_KEY for image backgrounds "
            "(or choose an OpenAI image model in Agent).",
            501,
            "NOT_IMPLEMENTED",
        )


def bedrock_configured() -> bool:
    """True when Bedrock should appear as an available text provider."""
    flag = (os.environ.get("BEDROCK_ENABLED") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if (os.environ.get("AI_PROVIDER") or "").lower().strip() == "bedrock":
        return True
    # Local AWS keys / profile — Lambda uses IAM role instead (set BEDROCK_ENABLED=true)
    if (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip() and (
        os.environ.get("AWS_SECRET_ACCESS_KEY") or ""
    ).strip():
        return True
    if (os.environ.get("AWS_PROFILE") or "").strip():
        return True
    return False


def _bedrock_runtime_client():
    import boto3

    region = (
        os.environ.get("BEDROCK_REGION")
        or os.environ.get("AWS_REGION")
        or "us-east-1"
    ).strip()
    return boto3.client("bedrock-runtime", region_name=region)


def _bedrock_extract_converse_text(resp: dict) -> str:
    try:
        parts = resp["output"]["message"]["content"]
        texts = [p.get("text") or "" for p in parts if isinstance(p, dict)]
        out = "\n".join(t for t in texts if t).strip()
        if out:
            return out
    except Exception:
        pass
    raise AppError(
        f"Bedrock returned empty/unreadable content: {str(resp)[:300]}",
        502,
        "BEDROCK_ERROR",
    )


class BedrockProvider(OpenAIProvider):
    """Amazon Bedrock via Converse API — chat/plan/score/insights.

    Images stay on image_providers (OpenAI, Titan, Nova Canvas, etc.).
    Enable models in the Bedrock console (Model access) for your account/region.
    """

    def __init__(self):
        self.api_key = ""  # unused; satisfies parent fields if referenced
        self.model = (
            os.environ.get("BEDROCK_MODEL")
            or "anthropic.claude-3-5-haiku-20241022-v1:0"
        ).strip()
        self.image_model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
        if not bedrock_configured():
            raise AppError(
                "Bedrock is not configured. Set BEDROCK_ENABLED=true "
                "(and AWS credentials or Lambda IAM), plus BEDROCK_MODEL.",
                500,
                "AI_CONFIG",
            )

    def _chat_json(self, system: str, user: str, temperature: float = 0.7) -> str:
        try:
            client = _bedrock_runtime_client()
            resp = client.converse(
                modelId=self.model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={
                    "temperature": float(temperature),
                    "maxTokens": 8192,
                },
            )
            return _bedrock_extract_converse_text(resp)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Bedrock error: {e}", 502, "BEDROCK_ERROR")

    def chat(self, message: str, context_pack: str, history: list[dict] | None = None) -> str:
        messages = []
        for h in (history or [])[-12:]:
            role = h.get("role") or "user"
            if role not in ("user", "assistant"):
                role = "user"
            # Converse: assistant → assistant
            messages.append(
                {
                    "role": "assistant" if role == "assistant" else "user",
                    "content": [{"text": h.get("content") or ""}],
                }
            )
        messages.append({"role": "user", "content": [{"text": message}]})
        try:
            client = _bedrock_runtime_client()
            resp = client.converse(
                modelId=self.model,
                system=[{"text": SYSTEM_STANCE + "\n\n" + context_pack}],
                messages=messages,
                inferenceConfig={"temperature": 0.7, "maxTokens": 4096},
            )
            return _bedrock_extract_converse_text(resp)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Bedrock chat error: {e}", 502, "BEDROCK_ERROR")

    def generate_image(self, prompt: str) -> bytes:
        # Compose path uses image_providers. Fallback to OpenAI if keyed.
        if (os.environ.get("OPENAI_API_KEY") or "").strip():
            return OpenAIProvider.generate_image(OpenAIProvider(), prompt)
        raise AppError(
            "Bedrock text only here — pick a Bedrock/OpenAI image model in Agent "
            "(Titan, Nova Canvas, gpt-image-1, …).",
            501,
            "NOT_IMPLEMENTED",
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


def list_text_providers() -> list[dict]:
    """Providers available for chat / plan / score (images stay separate)."""
    openai_ok = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    gemini_ok = bool((os.environ.get("GEMINI_API_KEY") or "").strip())
    bedrock_ok = bedrock_configured()
    default = (os.environ.get("AI_PROVIDER") or "openai").lower().strip()
    return [
        {
            "id": "openai",
            "label": "OpenAI",
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "available": openai_ok,
            "default": default == "openai",
        },
        {
            "id": "gemini",
            "label": "Google Gemini",
            "model": os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            "available": gemini_ok,
            "default": default == "gemini",
        },
        {
            "id": "bedrock",
            "label": "Amazon Bedrock",
            "model": os.environ.get(
                "BEDROCK_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0"
            ),
            "available": bedrock_ok,
            "default": default == "bedrock",
        },
        {
            "id": "stub",
            "label": "Stub (dev)",
            "model": "stub",
            "available": True,
            "default": default == "stub",
        },
    ]


def get_provider(name: str | None = None) -> AIProvider:
    resolved = (name or os.environ.get("AI_PROVIDER") or "openai").lower().strip()
    openai_key = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    gemini_key = bool((os.environ.get("GEMINI_API_KEY") or "").strip())
    logger.info(
        "AI provider resolve",
        {
            "provider": resolved,
            "openai_key_present": openai_key,
            "gemini_key_present": gemini_key,
            "bedrock_configured": bedrock_configured(),
        },
    )
    if resolved == "stub":
        return StubProvider()
    if resolved == "bedrock":
        return BedrockProvider()
    if resolved == "gemini":
        return GeminiProvider()
    if resolved == "openai":
        return OpenAIProvider()
    raise AppError(
        f"Unknown AI_PROVIDER={resolved}. Use openai | gemini | bedrock | stub.",
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
