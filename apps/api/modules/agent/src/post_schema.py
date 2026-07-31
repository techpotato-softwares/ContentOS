"""Structured LinkedIn post variant plans + deterministic validation."""
from __future__ import annotations
import json
import re
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


ANGLES = ("educational", "thought_leadership", "product_value")

LINKEDIN_PRESETS: dict = {
    # Higher than classic 1200×627 so text stays crisp when viewed large
    "linkedin_landscape": (1920, 1005),
    "linkedin_square": (1080, 1080),
    "linkedin_portrait": (1080, 1350),
}

DEFAULT_PRESET = "linkedin_landscape"

CAPTION_MIN_WORDS = {
    "short": 80,
    "medium": 150,
    "long": 220,
}


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


class SlidePlan(BaseModel):
    headline: str = ""
    body: str = ""
    visual_prompt: str = ""
    image_url: Optional[str] = None


class PostVariantPlan(BaseModel):
    angle: str
    headline: str = Field(min_length=1, max_length=160)
    subhead: str = ""
    bullets: List[str] = Field(default_factory=list)
    caption: str = ""
    background_prompt: str = ""
    # Compat alias filled from background_prompt
    image_prompt: str = ""
    format: str = "image"  # text | image | carousel
    slides: List[SlidePlan] = Field(default_factory=list)

    @field_validator("angle")
    @classmethod
    def normalize_angle(cls, v: str) -> str:
        v = (v or "").strip().lower().replace(" ", "_")
        if v not in ANGLES:
            return "educational"
        return v

    @field_validator("format")
    @classmethod
    def normalize_format(cls, v: str) -> str:
        v = (v or "image").strip().lower()
        if v not in ("text", "image", "carousel"):
            return "image"
        return v

    @field_validator("headline")
    @classmethod
    def headline_short(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("headline is required")
        words = v.split()
        if len(words) > 12:
            v = " ".join(words[:12])
        return v

    @field_validator("subhead")
    @classmethod
    def subhead_short(cls, v: str) -> str:
        v = (v or "").strip()
        words = v.split()
        if len(words) > 14:
            v = " ".join(words[:14])
        return v

    @field_validator("bullets")
    @classmethod
    def bullets_short(cls, v: list[str]) -> list[str]:
        out = []
        for b in (v or [])[:4]:
            s = (b or "").strip()
            if not s:
                continue
            words = s.split()
            if len(words) > 8:
                s = " ".join(words[:8])
            out.append(s)
        return out

    def model_post_init(self, __context: Any) -> None:
        if not self.background_prompt and self.image_prompt:
            object.__setattr__(self, "background_prompt", self.image_prompt)
        if not self.image_prompt and self.background_prompt:
            object.__setattr__(self, "image_prompt", self.background_prompt)

    def to_layout_dict(self) -> dict:
        d: dict[str, Any] = {
            "format": self.format,
            "angle": self.angle,
            "headline": self.headline,
            "subhead": self.subhead,
            "bullets": self.bullets,
            "caption": self.caption,
            "background_prompt": self.background_prompt,
        }
        if self.slides:
            d["slides"] = [
                {
                    "headline": s.headline,
                    "body": s.body,
                    "visual_prompt": s.visual_prompt,
                    **({"imageUrl": s.image_url} if s.image_url else {}),
                }
                for s in self.slides
            ]
        return d


def apply_banned_claims(plan: PostVariantPlan, banned: list[str]) -> PostVariantPlan:
    if not banned:
        return plan
    text_fields = [plan.headline, plan.subhead, plan.caption, *plan.bullets]
    blob = " ".join(text_fields).lower()
    for claim in banned:
        c = (claim or "").strip().lower()
        if c and c in blob:
            # Strip banned phrase from caption; keep structure
            plan.caption = re.sub(re.escape(claim), "", plan.caption, flags=re.I).strip()
    return plan


def _topic_tokens(brief: str) -> list[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "about", "into", "your",
        "our", "a", "an", "to", "of", "in", "on", "is", "are", "be", "as", "or",
        "create", "write", "post", "linkedin", "please", "make", "generate",
    }
    words = re.findall(r"[a-z0-9]{4,}", (brief or "").lower())
    out = []
    for w in words:
        if w in stop:
            continue
        if w not in out:
            out.append(w)
        if len(out) >= 8:
            break
    return out


def caption_meets_min(caption: str, length_pref: str = "medium") -> bool:
    pref = (length_pref or "medium").strip().lower()
    minimum = CAPTION_MIN_WORDS.get(pref, CAPTION_MIN_WORDS["medium"])
    return word_count(caption) >= max(40, int(minimum * 0.7))


def topic_fidelity_ok(brief: str, caption: str, headline: str = "") -> bool:
    tokens = _topic_tokens(brief)
    if len(tokens) < 2:
        return True
    blob = f"{headline} {caption}".lower()
    hits = sum(1 for t in tokens if t in blob)
    return hits >= min(2, len(tokens))


def parse_variant_plans(
    raw: list[dict] | str,
    *,
    format: str = "image",
    brief: str = "",
    length_pref: str = "medium",
) -> list[PostVariantPlan]:
    fmt = (format or "image").strip().lower()
    if fmt not in ("text", "image", "carousel"):
        fmt = "image"
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError("variants must be a list")

    limit = 1 if fmt == "carousel" else 3
    out: list[PostVariantPlan] = []
    for i, item in enumerate(raw[:limit]):
        if not isinstance(item, dict):
            continue
        slides_raw = item.get("slides") or []
        slides: list[dict] = []
        if isinstance(slides_raw, list):
            for s in slides_raw[:8]:
                if not isinstance(s, dict):
                    continue
                slides.append(
                    {
                        "headline": s.get("headline") or s.get("title") or f"Point {len(slides)+1}",
                        "body": s.get("body") or s.get("text") or "",
                        "visual_prompt": s.get("visual_prompt")
                        or s.get("background_prompt")
                        or "",
                        "image_url": s.get("imageUrl") or s.get("image_url"),
                    }
                )
        data = {
            "angle": item.get("angle") or ANGLES[min(i, 2)],
            "headline": item.get("headline")
            or item.get("title")
            or (item.get("caption") or "LinkedIn insight")[:60],
            "subhead": item.get("subhead") or item.get("subtitle") or "",
            "bullets": item.get("bullets") or item.get("features") or [],
            "caption": item.get("caption") or "",
            "background_prompt": item.get("background_prompt")
            or item.get("image_prompt")
            or item.get("imagePrompt")
            or "",
            "image_prompt": item.get("image_prompt") or item.get("imagePrompt") or "",
            "format": item.get("format") or fmt,
            "slides": slides,
        }
        if fmt == "text":
            data["background_prompt"] = ""
            data["image_prompt"] = ""
        elif fmt == "image" and not data["background_prompt"]:
            data["background_prompt"] = (
                f"Abstract corporate illustration background for: {data['headline']}. "
                "No text, letters, numbers, logos, or watermarks anywhere in the image."
            )
        elif fmt == "carousel" and len(data["slides"]) < 5:
            topic = (brief or data["headline"] or "topic").strip()
            while len(data["slides"]) < 5:
                n = len(data["slides"]) + 1
                data["slides"].append(
                    {
                        "headline": f"Insight {n}",
                        "body": f"Key point {n} about {topic[:80]}.",
                        "visual_prompt": (
                            f"Clean corporate slide background about {topic[:100]}, no text"
                        ),
                    }
                )
        plan = PostVariantPlan.model_validate(data)
        # Soft expand thin captions toward the floor using brief (avoid stock generic pad)
        if brief and (
            not caption_meets_min(plan.caption, length_pref)
            or not topic_fidelity_ok(brief, plan.caption, plan.headline)
        ):
            extra = (
                f"\n\nDiving deeper into this: {(brief or '')[:400].strip()}\n\n"
                "What should teams do next? Start with one concrete change this week, "
                "measure the outcome, and share what you learned with your network."
            )
            if extra.strip() not in (plan.caption or ""):
                plan.caption = ((plan.caption or "").rstrip() + extra).strip()
        out.append(plan)

    if fmt == "carousel":
        if not out:
            topic = (brief or "this topic").strip()
            out.append(
                PostVariantPlan(
                    angle="educational",
                    headline=topic[:60] or "Carousel insight",
                    subhead="A practical narrative",
                    caption=(
                        f"{topic}\n\nA clear walkthrough of the problem, insight, and next step "
                        "for teams who care about results.\n\n#LinkedIn"
                    ),
                    format="carousel",
                    slides=[
                        SlidePlan(
                            headline=f"Point {i}",
                            body=f"Detail {i} on {topic[:80]}",
                            visual_prompt=f"Slide about {topic[:80]}, no text",
                        )
                        for i in range(1, 6)
                    ],
                )
            )
        return out[:1]

    # Do not pad with unrelated stock templates when brief exists — retry-shaped fill from brief
    while len(out) < 3:
        angle = ANGLES[len(out)]
        topic = (brief or "this topic").strip()
        out.append(
            PostVariantPlan(
                angle=angle,
                headline=(topic[:50] or "Topic insight")[:60],
                subhead="On-topic perspective",
                bullets=["Insight", "Action", "Outcome"],
                caption=(
                    f"{topic}\n\n"
                    f"An {angle.replace('_', ' ')} angle on this topic: why it matters, "
                    "what often goes wrong, and one practical next step you can take this week. "
                    "Reply with your experience — specific stories help everyone learn faster.\n\n"
                    "#LinkedIn"
                ),
                background_prompt=(
                    f"Soft abstract corporate background about {topic[:100]}, "
                    "no text, no letters, no logos, no watermarks"
                    if fmt == "image"
                    else ""
                ),
                format=fmt,
            )
        )
    return out[:3]
