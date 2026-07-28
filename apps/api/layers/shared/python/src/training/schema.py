"""TenantTrainingSchema v1 — structured company records for consistent generation."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class OfferingItem(BaseModel):
    name: str
    description: str = ""
    differentiators: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)


class FaqItem(BaseModel):
    question: str
    answer: str


class DocumentRef(BaseModel):
    title: str
    category: Literal["product", "case_study", "guideline", "other"] = "other"
    body: str
    priority: int = 100


class CompanySection(BaseModel):
    legal_name: str = ""
    display_name: str = ""
    industry: str = ""
    website: str = ""
    phone: str = ""
    email: str = ""
    hq_location: str = ""
    operating_regions: list[str] = Field(default_factory=list)
    company_size_band: str = ""
    founded_year: Optional[int] = None
    one_liner: str = Field(default="", max_length=160)


class AudienceSection(BaseModel):
    icp_titles: list[str] = Field(default_factory=list)
    icp_industries: list[str] = Field(default_factory=list)
    buyer_pain_points: list[str] = Field(default_factory=list)
    linkedin_audience_notes: str = ""


class MessagingSection(BaseModel):
    tone: list[str] = Field(default_factory=list)
    voice_dos: list[str] = Field(default_factory=list)
    voice_donts: list[str] = Field(default_factory=list)
    banned_claims: list[str] = Field(default_factory=list)
    compliance_notes: str = ""
    cta_styles: list[str] = Field(default_factory=list)
    hashtag_policy: str = ""
    linkedin_post_length_preference: str = "medium"


class BrandVisualSection(BaseModel):
    primary_color: str = ""
    secondary_color: str = ""
    accent_color: str = ""
    logo_url: str = ""
    visual_style_keywords: list[str] = Field(default_factory=list)
    image_do_nots: list[str] = Field(default_factory=list)
    app_display_name: str = ""
    ui_mode: Literal["platform", "white_label"] = "platform"

    @field_validator("primary_color", "secondary_color", "accent_color")
    @classmethod
    def normalize_hex(cls, v: str) -> str:
        if not v:
            return v
        v = v.strip()
        if v and not v.startswith("#"):
            v = f"#{v}"
        return v


class TenantTrainingSchema(BaseModel):
    schema_version: str = "1"
    company: CompanySection = Field(default_factory=CompanySection)
    audience: AudienceSection = Field(default_factory=AudienceSection)
    offerings: list[OfferingItem] = Field(default_factory=list)
    messaging: MessagingSection = Field(default_factory=MessagingSection)
    brand_visual: BrandVisualSection = Field(default_factory=BrandVisualSection)
    approved_facts: list[str] = Field(default_factory=list)
    faq: list[FaqItem] = Field(default_factory=list)
    documents: list[DocumentRef] = Field(default_factory=list)


def empty_training() -> TenantTrainingSchema:
    return TenantTrainingSchema()


def parse_training(raw: str | dict | None) -> TenantTrainingSchema:
    if raw is None or raw == "" or raw == "{}":
        return empty_training()
    if isinstance(raw, str):
        return TenantTrainingSchema.model_validate_json(raw)
    return TenantTrainingSchema.model_validate(raw)


def is_white_label_complete(brand: BrandVisualSection) -> bool:
    return bool(
        brand.ui_mode == "white_label"
        and brand.logo_url
        and brand.primary_color
        and brand.secondary_color
        and brand.accent_color
    )


CONTEXT_PACK_BUDGET = 7500


def render_context_pack(
    training: TenantTrainingSchema,
    extra_docs: list[DocumentRef] | None = None,
) -> str:
    """Deterministic markdown context pack — same headers every time."""
    docs = list(training.documents) + list(extra_docs or [])
    docs.sort(key=lambda d: d.priority)

    c = training.company
    a = training.audience
    m = training.messaging
    b = training.brand_visual

    sections: list[str] = [
        "# COMPANY CONTEXT (for brand consistency — not a topic allowlist)",
        "## Company",
        f"- Legal name: {c.legal_name}",
        f"- Display name: {c.display_name}",
        f"- Industry: {c.industry}",
        f"- Website: {c.website}",
        f"- Phone: {c.phone}",
        f"- Email: {c.email}",
        f"- HQ: {c.hq_location}",
        f"- Regions: {', '.join(c.operating_regions)}",
        f"- Size: {c.company_size_band}",
        f"- Founded: {c.founded_year or ''}",
        f"- One-liner: {c.one_liner}",
        "## Audience",
        f"- ICP titles: {', '.join(a.icp_titles)}",
        f"- ICP industries: {', '.join(a.icp_industries)}",
        f"- Pain points: {', '.join(a.buyer_pain_points)}",
        f"- LinkedIn notes: {a.linkedin_audience_notes}",
        "## Offerings",
    ]
    for o in training.offerings:
        sections.append(
            f"- {o.name}: {o.description} | diff: {', '.join(o.differentiators)} | proof: {', '.join(o.proof_points)}"
        )
    sections.extend(
        [
            "## Messaging",
            f"- Tone: {', '.join(m.tone)}",
            f"- Do: {', '.join(m.voice_dos)}",
            f"- Don't: {', '.join(m.voice_donts)}",
            f"- Banned claims: {', '.join(m.banned_claims)}",
            f"- Compliance: {m.compliance_notes}",
            f"- CTA styles: {', '.join(m.cta_styles)}",
            f"- Hashtags: {m.hashtag_policy}",
            f"- Length: {m.linkedin_post_length_preference}",
            "## Brand visual",
            f"- Colors: primary={b.primary_color} secondary={b.secondary_color} accent={b.accent_color}",
            f"- Logo: {b.logo_url}",
            f"- Style keywords: {', '.join(b.visual_style_keywords)}",
            f"- Image do-nots: {', '.join(b.image_do_nots)}",
            "## Approved facts",
        ]
    )
    for f in training.approved_facts:
        sections.append(f"- {f}")
    sections.append("## FAQ")
    for q in training.faq:
        sections.append(f"- Q: {q.question}\n  A: {q.answer}")
    sections.append("## Documents")

    pack = "\n".join(sections)
    for d in docs:
        chunk = f"\n### [{d.category}] {d.title} (priority {d.priority})\n{d.body}\n"
        if len(pack) + len(chunk) > CONTEXT_PACK_BUDGET:
            break
        pack += chunk

    pack += (
        "\n## Generation rules\n"
        "- Use this context for brand voice, colors, and known company facts.\n"
        "- Fulfill the user's request even if the topic is not listed above.\n"
        "- Do not invent false company metrics, clients, or awards.\n"
    )
    return pack[:CONTEXT_PACK_BUDGET]


def resolve_ui_theme(training: TenantTrainingSchema, tenant_fields: dict | None = None) -> dict:
    """Return theme payload for SPA. Defaults to platform when white-label incomplete."""
    brand = training.brand_visual
    # Prefer live tenant columns if provided
    if tenant_fields:
        brand = BrandVisualSection(
            primary_color=tenant_fields.get("primary_color") or brand.primary_color,
            secondary_color=tenant_fields.get("secondary_color") or brand.secondary_color,
            accent_color=tenant_fields.get("accent_color") or brand.accent_color,
            logo_url=tenant_fields.get("logo_url") or brand.logo_url,
            app_display_name=tenant_fields.get("app_display_name") or brand.app_display_name,
            ui_mode=tenant_fields.get("ui_mode") or brand.ui_mode,  # type: ignore[arg-type]
            visual_style_keywords=brand.visual_style_keywords,
            image_do_nots=brand.image_do_nots,
        )

    if is_white_label_complete(brand):
        return {
            "source": "tenant",
            "uiMode": "white_label",
            "appDisplayName": brand.app_display_name or training.company.display_name or "ContentOS",
            "logoUrl": brand.logo_url,
            "colors": {
                "primary": brand.primary_color,
                "secondary": brand.secondary_color,
                "accent": brand.accent_color,
            },
        }

    return {
        "source": "platform",
        "uiMode": "platform",
        "appDisplayName": "ContentOS",
        "logoUrl": None,
        "colors": {
            "primary": "#0d9488",
            "secondary": "#134e4a",
            "accent": "#2dd4bf",
        },
    }
