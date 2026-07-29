"""Structured LinkedIn post variant plans + deterministic validation."""
from __future__ import annotations
import json
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator


ANGLES = ("educational", "thought_leadership", "product_value")

LINKEDIN_PRESETS: dict[str, tuple[int, int]] = {
    # Higher than classic 1200×627 so text stays crisp when viewed large
    "linkedin_landscape": (1920, 1005),
    "linkedin_square": (1080, 1080),
    "linkedin_portrait": (1080, 1350),
}

DEFAULT_PRESET = "linkedin_landscape"


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", (text or "").strip()) if w])


class PostVariantPlan(BaseModel):
    angle: str
    headline: str = Field(min_length=1, max_length=120)
    subhead: str = ""
    bullets: list[str] = Field(default_factory=list)
    caption: str = ""
    background_prompt: str = ""
    # Compat alias filled from background_prompt
    image_prompt: str = ""

    @field_validator("angle")
    @classmethod
    def normalize_angle(cls, v: str) -> str:
        v = (v or "").strip().lower().replace(" ", "_")
        if v not in ANGLES:
            return "educational"
        return v

    @field_validator("headline")
    @classmethod
    def headline_short(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("headline is required")
        words = v.split()
        if len(words) > 7:
            v = " ".join(words[:7])
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
            if len(words) > 5:
                s = " ".join(words[:5])
            out.append(s)
        return out

    def model_post_init(self, __context: Any) -> None:
        if not self.background_prompt and self.image_prompt:
            object.__setattr__(self, "background_prompt", self.image_prompt)
        if not self.image_prompt and self.background_prompt:
            object.__setattr__(self, "image_prompt", self.background_prompt)

    def to_layout_dict(self) -> dict:
        return {
            "angle": self.angle,
            "headline": self.headline,
            "subhead": self.subhead,
            "bullets": self.bullets,
            "caption": self.caption,
            "background_prompt": self.background_prompt,
        }


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


def parse_variant_plans(raw: list[dict] | str) -> list[PostVariantPlan]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError("variants must be a list")
    out: list[PostVariantPlan] = []
    for i, item in enumerate(raw[:3]):
        if not isinstance(item, dict):
            continue
        # Normalize keys from older / alternate shapes
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
        }
        if not data["background_prompt"]:
            data["background_prompt"] = (
                f"Abstract corporate illustration background for: {data['headline']}. "
                "No text, letters, numbers, logos, or watermarks anywhere in the image."
            )
        out.append(PostVariantPlan.model_validate(data))
    while len(out) < 3:
        angle = ANGLES[len(out)]
        out.append(
            PostVariantPlan(
                angle=angle,
                headline="Drive better outcomes",
                subhead="Insights for modern B2B teams",
                bullets=["Clarity", "Speed", "Trust"],
                caption="Share your perspective with your network.",
                background_prompt=(
                    "Soft abstract teal corporate background, gradient shapes, no text, "
                    "no letters, no logos, no watermarks"
                ),
            )
        )
    return out[:3]
