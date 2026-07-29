"""Deterministic LinkedIn post composition — text + logo overlay on AI background."""
from __future__ import annotations
import io
import os
from pathlib import Path
from typing import Optional
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageColor

API_ROOT = Path(__file__).resolve().parents[3]
MEDIA_ROOT = API_ROOT / "media"

# Prefer common system fonts; fall back to default bitmap font
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    ordered = _FONT_CANDIDATES if bold else list(reversed(_FONT_CANDIDATES[:4])) + _FONT_CANDIDATES
    for path in ordered:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex(color: str, fallback: str) -> tuple[int, int, int]:
    try:
        return ImageColor.getrgb(color or fallback)[:3]
    except Exception:
        return ImageColor.getrgb(fallback)[:3]


def _resolve_logo_bytes(logo_url: Optional[str], tenant_id: int) -> Optional[bytes]:
    if not logo_url:
        # Convention path
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = MEDIA_ROOT / f"tenants/{tenant_id}/brand/logo.{ext}"
            if p.exists():
                return p.read_bytes()
        return None
    if logo_url.startswith("/media/"):
        local = MEDIA_ROOT / logo_url[len("/media/") :]
        if local.exists():
            return local.read_bytes()
    if logo_url.startswith("http://") or logo_url.startswith("https://"):
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(logo_url)
                if r.status_code < 400:
                    return r.content
        except Exception:
            return None
    # Relative path under media
    candidate = MEDIA_ROOT / logo_url.lstrip("/")
    if candidate.exists():
        return candidate.read_bytes()
    return None


def _fit_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    src = img.convert("RGBA")
    scale = max(width / src.width, height / src.height)
    nw, nh = int(src.width * scale), int(src.height * scale)
    src = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - width) // 2
    top = (nh - height) // 2
    return src.crop((left, top, left + width, top + height))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def compose_linkedin_post(
    background_bytes: bytes,
    layout: dict,
    *,
    width: int,
    height: int,
    brand: dict,
    tenant_id: int,
) -> bytes:
    """Overlay exact headline/subhead/bullets/footer/logo onto an AI background."""
    bg = Image.open(io.BytesIO(background_bytes))
    canvas = _fit_cover(bg, width, height)

    primary = _hex(brand.get("primary_color") or "#0d9488", "#0d9488")
    secondary = _hex(brand.get("secondary_color") or "#134e4a", "#134e4a")
    accent = _hex(brand.get("accent_color") or "#2dd4bf", "#2dd4bf")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Left content panel
    panel_w = int(width * 0.52)
    draw.rectangle([(0, 0), (panel_w, height)], fill=(*secondary, 210))
    # Accent bar
    draw.rectangle([(0, 0), (10, height)], fill=(*accent, 255))
    # Footer strip
    footer_h = max(48, int(height * 0.09))
    draw.rectangle([(0, height - footer_h), (width, height)], fill=(*primary, 235))

    pad = int(width * 0.04)
    text_max = panel_w - pad * 2

    headline = (layout.get("headline") or "").strip()
    subhead = (layout.get("subhead") or "").strip()
    bullets = layout.get("bullets") or []
    company = (brand.get("display_name") or brand.get("company_name") or "").strip()

    # Logo
    logo_bytes = _resolve_logo_bytes(brand.get("logo_url"), tenant_id)
    y = pad
    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            max_h = max(36, int(height * 0.1))
            max_w = int(panel_w * 0.35)
            ratio = min(max_w / logo.width, max_h / logo.height)
            logo = logo.resize((max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio))), Image.Resampling.LANCZOS)
            overlay.paste(logo, (pad, y), logo)
            y += logo.height + int(pad * 0.6)
        except Exception:
            pass
    elif company:
        font_co = _load_font(max(18, int(height * 0.035)), bold=True)
        draw.text((pad, y), company[:40], font=font_co, fill=(255, 255, 255, 240))
        y += int(height * 0.06)

    # Headline
    font_h = _load_font(max(28, int(height * 0.07)), bold=True)
    for line in _wrap(draw, headline, font_h, text_max)[:3]:
        draw.text((pad, y), line, font=font_h, fill=(255, 255, 255, 255))
        y += int(font_h.size * 1.2)
    y += int(pad * 0.4)

    if subhead:
        font_s = _load_font(max(16, int(height * 0.035)))
        for line in _wrap(draw, subhead, font_s, text_max)[:3]:
            draw.text((pad, y), line, font=font_s, fill=(204, 251, 241, 240))
            y += int(font_s.size * 1.25)
        y += int(pad * 0.35)

    font_b = _load_font(max(15, int(height * 0.032)))
    for b in bullets[:4]:
        line = f"• {b}"
        for wrapped in _wrap(draw, line, font_b, text_max)[:2]:
            draw.text((pad, y), wrapped, font=font_b, fill=(255, 255, 255, 230))
            y += int(font_b.size * 1.3)
        if y > height - footer_h - pad:
            break

    # Footer contact
    footer_bits = []
    if brand.get("website"):
        footer_bits.append(str(brand["website"]))
    if brand.get("phone"):
        footer_bits.append(str(brand["phone"]))
    if brand.get("email"):
        footer_bits.append(str(brand["email"]))
    if footer_bits:
        font_f = _load_font(max(12, int(height * 0.028)))
        footer_text = "  ·  ".join(footer_bits)
        # Truncate if needed
        while draw.textlength(footer_text, font=font_f) > width - pad * 2 and len(footer_text) > 10:
            footer_text = footer_text[:-4] + "…"
        ty = height - footer_h + (footer_h - font_f.size) // 2
        draw.text((pad, ty), footer_text, font=font_f, fill=(255, 255, 255, 245))

    composed = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    out = io.BytesIO()
    composed.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
