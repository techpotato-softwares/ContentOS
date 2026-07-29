"""Deterministic LinkedIn post composition — crisp text + logo on AI background.

Renders at 2× then downscales (LANCZOS) so type stays sharp on retina / LinkedIn.
Left panel is a soft gradient so the subject on the right stays visible.
"""
from __future__ import annotations
import io
import os
from pathlib import Path
from typing import Optional
import httpx
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageEnhance

API_ROOT = Path(__file__).resolve().parents[3]
MEDIA_ROOT = API_ROOT / "media"

# Prefer crisp TrueType/OpenType faces (macOS + Linux + Windows)
_BOLD_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "/Library/Fonts/Helvetica Neue Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\segoeuib.ttf",
]
_REG_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/Library/Fonts/Helvetica Neue.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
]

# Supersample factor for sharp glyphs
RENDER_SCALE = max(2, int(os.environ.get("COMPOSE_SCALE", "2") or "2"))


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = _BOLD_FONTS if bold else _REG_FONTS
    for path in paths:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            # .ttc collections sometimes need an index
            try:
                return ImageFont.truetype(path, size=size, index=0)
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
    candidate = MEDIA_ROOT / logo_url.lstrip("/")
    if candidate.exists():
        return candidate.read_bytes()
    return None


def _fit_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    src = img.convert("RGBA")
    scale = max(width / max(src.width, 1), height / max(src.height, 1))
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
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


def _draw_text_crisp(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    shadow: bool = True,
) -> None:
    """Draw text with a soft shadow for contrast (no blur on the glyph itself)."""
    x, y = xy
    if shadow:
        draw.text((x + 1, y + 2), text, font=font, fill=(0, 0, 0, 90))
    draw.text((x, y), text, font=font, fill=fill)


def background_looks_empty(background_bytes: bytes, *, right_ratio: float = 0.45) -> bool:
    """Heuristic: right side nearly uniform / near-black → treat as missing visual."""
    try:
        im = Image.open(io.BytesIO(background_bytes)).convert("RGB")
        w, h = im.size
        left = int(w * (1 - right_ratio))
        crop = im.crop((left, 0, w, h)).resize((64, 64), Image.Resampling.BILINEAR)
        pixels = list(crop.getdata())
        if not pixels:
            return True
        # Mean luminance + stddev
        lum = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels]
        mean = sum(lum) / len(lum)
        var = sum((v - mean) ** 2 for v in lum) / len(lum)
        std = var ** 0.5
        # Very dark void OR almost no detail
        if mean < 18 and std < 12:
            return True
        if std < 8:
            return True
        return False
    except Exception:
        return False


def enrich_background_prompt(prompt: str, brand: dict | None = None) -> str:
    """Force a full-bleed subject on the RIGHT so template text has a real visual."""
    brand = brand or {}
    colors = ", ".join(
        filter(
            None,
            [
                brand.get("primary_color"),
                brand.get("secondary_color"),
                brand.get("accent_color"),
            ],
        )
    )
    style = ", ".join((brand.get("visual_style_keywords") or [])[:6])
    base = (prompt or "").strip()
    return (
        f"{base}\n\n"
        "COMPOSITION (mandatory):\n"
        "- Full-bleed landscape 16:9 / ~1.91:1, edge-to-edge — NO black bars, letterboxing, or empty voids.\n"
        "- Put the MAIN SUBJECT on the RIGHT 55% of the frame (person at work, product UI, device, "
        "polished 3D object, or vivid abstract sculpture). Subject must be sharp and recognizable.\n"
        "- LEFT 40% should be softer / simpler / slightly blurred so text can overlay later.\n"
        "- Photoreal or premium corporate illustration; rich detail and depth of field.\n"
        f"{('- Subtle color accents: ' + colors) if colors else ''}\n"
        f"{('- Style keywords: ' + style) if style else ''}\n"
        "CRITICAL: Absolutely NO text, letters, numbers, logos, watermarks, or UI captions."
    ).strip()


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
    scale = RENDER_SCALE
    W, H = width * scale, height * scale

    bg = Image.open(io.BytesIO(background_bytes))
    # Slight contrast lift so soft AI backgrounds don't look washed out
    canvas = _fit_cover(bg, W, H)
    try:
        canvas = ImageEnhance.Contrast(canvas.convert("RGB")).enhance(1.06).convert("RGBA")
    except Exception:
        canvas = canvas.convert("RGBA")

    primary = _hex(brand.get("primary_color") or "#0d9488", "#0d9488")
    secondary = _hex(brand.get("secondary_color") or "#134e4a", "#134e4a")
    accent = _hex(brand.get("accent_color") or "#2dd4bf", "#2dd4bf")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Soft left scrim (gradient) — keeps right subject visible
    panel_w = int(W * 0.46)
    fade_w = int(W * 0.12)
    for x in range(panel_w + fade_w):
        if x < panel_w:
            alpha = 200
        else:
            t = (x - panel_w) / max(fade_w, 1)
            alpha = int(200 * (1 - t))
        draw.line([(x, 0), (x, H)], fill=(*secondary, alpha))

    # Thin accent rail
    rail = max(6, int(W * 0.006))
    draw.rectangle([(0, 0), (rail, H)], fill=(*accent, 255))

    # Footer strip (slightly translucent so photo bleeds through)
    footer_h = max(56 * scale, int(H * 0.085))
    draw.rectangle([(0, H - footer_h), (W, H)], fill=(*primary, 230))

    pad = int(W * 0.035)
    text_max = panel_w - pad * 2

    headline = (layout.get("headline") or "").strip()
    subhead = (layout.get("subhead") or "").strip()
    bullets = layout.get("bullets") or []
    company = (brand.get("display_name") or brand.get("company_name") or "").strip()

    y = pad
    logo_bytes = _resolve_logo_bytes(brand.get("logo_url"), tenant_id)
    if logo_bytes:
        try:
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            max_h = max(40 * scale, int(H * 0.09))
            max_w = int(panel_w * 0.38)
            ratio = min(max_w / max(logo.width, 1), max_h / max(logo.height, 1))
            logo = logo.resize(
                (max(1, int(logo.width * ratio)), max(1, int(logo.height * ratio))),
                Image.Resampling.LANCZOS,
            )
            overlay.paste(logo, (pad, y), logo)
            y += logo.height + int(pad * 0.55)
        except Exception:
            pass
    elif company:
        font_co = _load_font(max(22 * scale, int(H * 0.032)), bold=True)
        _draw_text_crisp(draw, (pad, y), company[:42], font=font_co, fill=(255, 255, 255, 235))
        y += int(H * 0.055)

    # Headline — larger, tighter leading
    font_h = _load_font(max(44 * scale, int(H * 0.078)), bold=True)
    for line in _wrap(draw, headline, font_h, text_max)[:3]:
        _draw_text_crisp(draw, (pad, y), line, font=font_h, fill=(255, 255, 255, 255))
        y += int(getattr(font_h, "size", 44 * scale) * 1.15)
    y += int(pad * 0.35)

    if subhead:
        font_s = _load_font(max(24 * scale, int(H * 0.036)))
        for line in _wrap(draw, subhead, font_s, text_max)[:3]:
            _draw_text_crisp(
                draw, (pad, y), line, font=font_s, fill=(204, 251, 241, 245), shadow=True
            )
            y += int(getattr(font_s, "size", 24 * scale) * 1.28)
        y += int(pad * 0.3)

    font_b = _load_font(max(22 * scale, int(H * 0.033)))
    for b in bullets[:4]:
        line = f"•  {b}"
        for wrapped in _wrap(draw, line, font_b, text_max)[:2]:
            _draw_text_crisp(
                draw, (pad, y), wrapped, font=font_b, fill=(255, 255, 255, 240), shadow=True
            )
            y += int(getattr(font_b, "size", 22 * scale) * 1.35)
        if y > H - footer_h - pad:
            break

    footer_bits = []
    if brand.get("website"):
        footer_bits.append(str(brand["website"]).replace("https://", "").replace("http://", ""))
    if brand.get("phone"):
        footer_bits.append(str(brand["phone"]))
    if brand.get("email"):
        footer_bits.append(str(brand["email"]))
    if footer_bits:
        font_f = _load_font(max(18 * scale, int(H * 0.026)))
        footer_text = "   ·   ".join(footer_bits)
        while draw.textlength(footer_text, font=font_f) > W - pad * 2 and len(footer_text) > 12:
            footer_text = footer_text[:-5] + "…"
        ty = H - footer_h + (footer_h - getattr(font_f, "size", 18 * scale)) // 2
        _draw_text_crisp(
            draw, (pad, ty), footer_text, font=font_f, fill=(255, 255, 255, 250), shadow=False
        )

    composed = Image.alpha_composite(canvas, overlay)
    # Downscale 2× → target for razor-sharp type
    if scale > 1:
        composed = composed.resize((width, height), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    # PNG, no palette quantization; compress_level trades size vs speed (not quality)
    composed.convert("RGB").save(out, format="PNG", compress_level=6)
    return out.getvalue()
