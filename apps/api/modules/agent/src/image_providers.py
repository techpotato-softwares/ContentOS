"""Image background generation adapters + capability registry."""
from __future__ import annotations
import base64
import os
from dataclasses import dataclass
from typing import Optional
import httpx
from middleware.error_handler import AppError


@dataclass
class ImageModelInfo:
    id: str
    label: str
    provider: str
    native_text_quality: str  # poor | fair | good | best
    best_for: str
    supported_sizes: list[str]
    cost_hint: str
    available: bool
    env_key: str = ""


class ImageBackgroundProvider:
    model_id: str = "stub"

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        raise NotImplementedError


class StubImageProvider(ImageBackgroundProvider):
    model_id = "stub"

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        # Minimal valid PNG 1x1 expanded by compose
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )


class OpenAIImageProvider(ImageBackgroundProvider):
    def __init__(self, model_id: str = "gpt-image-1"):
        self.model_id = model_id
        self.api_key = (os.environ.get("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
        if not self.api_key:
            raise AppError("OPENAI_API_KEY missing", 500, "AI_CONFIG")

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        model = self.model_id
        gpt_sizes = ("1024x1024", "1536x1024", "1024x1536", "auto")
        if model.startswith("gpt-image") and size not in gpt_sizes:
            size = "1536x1024"
        if model.startswith("dall-e-3") and size not in ("1024x1024", "1792x1024", "1024x1792"):
            size = "1792x1024"

        # Force no-text backgrounds
        safe_prompt = (
            f"{prompt.strip()}\n\n"
            "CRITICAL: Pure visual background only. Absolutely no text, letters, numbers, "
            "watermarks, logos, captions, or typography of any kind."
        )[:3900]

        payload = {"model": model, "prompt": safe_prompt, "n": 1, "size": size}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=180.0) as client:
            r = client.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
            if r.status_code >= 400:
                for fallback in ("1536x1024", "1792x1024", "1024x1024"):
                    if fallback == payload.get("size"):
                        continue
                    if model.startswith("gpt-image") and fallback not in gpt_sizes:
                        continue
                    payload["size"] = fallback
                    r = client.post(
                        "https://api.openai.com/v1/images/generations",
                        headers=headers,
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
            if data.get("b64_json"):
                return base64.b64decode(data["b64_json"])
            url = data.get("url")
            if url:
                img = client.get(url, timeout=120.0)
                img.raise_for_status()
                return img.content
            raise AppError("OpenAI image missing b64_json/url", 502, "OPENAI_IMAGE_ERROR")


class MissingKeyImageProvider(ImageBackgroundProvider):
    def __init__(self, model_id: str, env_key: str):
        self.model_id = model_id
        self.env_key = env_key

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        raise AppError(
            f"Model '{self.model_id}' requires {self.env_key} to be set.",
            501,
            "IMAGE_PROVIDER_NOT_CONFIGURED",
        )


REGISTRY: list[ImageModelInfo] = [
    ImageModelInfo(
        id="gpt-image-1",
        label="GPT Image 1 (OpenAI)",
        provider="openai",
        native_text_quality="fair",
        best_for="General backgrounds; pair with template overlay",
        supported_sizes=["1024x1024", "1536x1024", "1024x1536"],
        cost_hint="Standard OpenAI image pricing",
        available=True,
        env_key="OPENAI_API_KEY",
    ),
    ImageModelInfo(
        id="dall-e-3",
        label="DALL·E 3 (OpenAI)",
        provider="openai",
        native_text_quality="poor",
        best_for="Illustrative backgrounds only (avoid native text)",
        supported_sizes=["1024x1024", "1792x1024", "1024x1792"],
        cost_hint="OpenAI DALL·E 3 pricing",
        available=True,
        env_key="OPENAI_API_KEY",
    ),
    ImageModelInfo(
        id="ideogram",
        label="Ideogram",
        provider="ideogram",
        native_text_quality="best",
        best_for="Native on-image text (experimental mode)",
        supported_sizes=["1024x1024"],
        cost_hint="Requires IDEOGRAM_API_KEY",
        available=False,
        env_key="IDEOGRAM_API_KEY",
    ),
    ImageModelInfo(
        id="recraft",
        label="Recraft",
        provider="recraft",
        native_text_quality="good",
        best_for="Flat / infographic style",
        supported_sizes=["1024x1024"],
        cost_hint="Requires RECRAFT_API_KEY",
        available=False,
        env_key="RECRAFT_API_KEY",
    ),
    ImageModelInfo(
        id="stub",
        label="Stub (dev)",
        provider="stub",
        native_text_quality="poor",
        best_for="Local UI testing without image API spend",
        supported_sizes=["1024x1024"],
        cost_hint="Free",
        available=True,
        env_key="",
    ),
]


def list_image_models() -> list[dict]:
    out = []
    for m in REGISTRY:
        available = m.available
        if m.env_key and not (os.environ.get(m.env_key) or "").strip():
            available = m.id == "stub"
        if m.provider == "openai":
            available = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
        if m.id == "stub":
            available = True
        if m.env_key in ("IDEOGRAM_API_KEY", "RECRAFT_API_KEY"):
            available = bool((os.environ.get(m.env_key) or "").strip())
        out.append(
            {
                "id": m.id,
                "label": m.label,
                "provider": m.provider,
                "nativeTextQuality": m.native_text_quality,
                "bestFor": m.best_for,
                "supportedSizes": m.supported_sizes,
                "costHint": m.cost_hint,
                "available": available,
            }
        )
    return out


def get_image_provider(model_id: Optional[str] = None) -> ImageBackgroundProvider:
    mid = (model_id or os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip()
    if mid == "stub" or (os.environ.get("AI_PROVIDER") or "").lower() == "stub":
        return StubImageProvider()
    if mid in ("gpt-image-1", "dall-e-3", "gpt-image-1-mini"):
        return OpenAIImageProvider(mid if mid != "gpt-image-1-mini" else "gpt-image-1")
    if mid == "ideogram":
        if (os.environ.get("IDEOGRAM_API_KEY") or "").strip():
            return MissingKeyImageProvider("ideogram", "IDEOGRAM_API_KEY")  # placeholder until wired
        return MissingKeyImageProvider("ideogram", "IDEOGRAM_API_KEY")
    if mid == "recraft":
        return MissingKeyImageProvider("recraft", "RECRAFT_API_KEY")
    # Default OpenAI
    return OpenAIImageProvider(os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"))


def nearest_gen_size(preset_w: int, preset_h: int, model_id: str) -> str:
    """Map LinkedIn preset to a provider-supported generation size."""
    ratio = preset_w / max(preset_h, 1)
    if model_id.startswith("dall-e"):
        if ratio > 1.2:
            return "1792x1024"
        if ratio < 0.85:
            return "1024x1792"
        return "1024x1024"
    if ratio > 1.2:
        return "1536x1024"
    if ratio < 0.85:
        return "1024x1536"
    return "1024x1024"
