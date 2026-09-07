"""Image background generation adapters + capability registry."""
from __future__ import annotations

import base64
import json
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


def _safe_visual_prompt(prompt: str, max_len: int = 3900) -> str:
    return (
        f"{prompt.strip()}\n\n"
        "CRITICAL: Pure visual background only. Absolutely no text, letters, numbers, "
        "watermarks, logos, captions, or typography of any kind."
    )[:max_len]


def _parse_wh(size: str, default: tuple[int, int] = (1536, 1024)) -> tuple[int, int]:
    try:
        w, h = size.lower().split("x", 1)
        return int(w), int(h)
    except Exception:
        return default


def bedrock_image_configured() -> bool:
    flag = (os.environ.get("BEDROCK_ENABLED") or "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if (os.environ.get("AI_PROVIDER") or "").lower().strip() == "bedrock":
        return True
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


class OpenAIImageProvider(ImageBackgroundProvider):
    def __init__(self, model_id: str = "gpt-image-1", api_key: str | None = None):
        self.model_id = model_id
        self.api_key = (
            (api_key if api_key is not None else os.environ.get("OPENAI_API_KEY") or "")
            .strip()
            .strip('"')
            .strip("'")
        )
        if not self.api_key:
            raise AppError("OPENAI_API_KEY missing", 500, "AI_CONFIG")

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        model = self.model_id
        gpt_sizes = ("1024x1024", "1536x1024", "1024x1536", "auto")
        if model.startswith("gpt-image") and size not in gpt_sizes:
            size = "1536x1024"
        if model.startswith("dall-e-3") and size not in ("1024x1024", "1792x1024", "1024x1792"):
            size = "1792x1024"

        safe_prompt = _safe_visual_prompt(prompt)
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


class BedrockImageProvider(ImageBackgroundProvider):
    """Amazon Titan Image, Nova Canvas, or Stability models on Bedrock."""

    # Map UI ids → Bedrock model IDs (override via BEDROCK_*_MODEL env)
    MODEL_IDS = {
        "bedrock-titan": "amazon.titan-image-generator-v2:0",
        "bedrock-nova-canvas": "amazon.nova-canvas-v1:0",
        "bedrock-sdxl": "stability.stable-diffusion-xl-v1",
        "bedrock-stable-image": "stability.stable-image-core-v1:0",
    }

    def __init__(self, model_id: str = "bedrock-titan"):
        self.model_id = model_id
        if not bedrock_image_configured():
            raise AppError(
                "Bedrock images require BEDROCK_ENABLED=true (or AWS credentials) "
                "and model access enabled in the Bedrock console.",
                500,
                "AI_CONFIG",
            )
        env_override = {
            "bedrock-titan": "BEDROCK_TITAN_MODEL",
            "bedrock-nova-canvas": "BEDROCK_NOVA_CANVAS_MODEL",
            "bedrock-sdxl": "BEDROCK_SDXL_MODEL",
            "bedrock-stable-image": "BEDROCK_STABLE_IMAGE_MODEL",
        }.get(model_id)
        self.bedrock_model = (
            (os.environ.get(env_override) if env_override else None)
            or self.MODEL_IDS.get(model_id)
            or self.MODEL_IDS["bedrock-titan"]
        ).strip()

    def _snap_size(self, size: str) -> tuple[int, int]:
        w, h = _parse_wh(size)
        # Titan / Nova Canvas prefer multiples of 64 within common bounds
        def clamp(n: int) -> int:
            n = max(512, min(1536, n))
            return (n // 64) * 64

        return clamp(w), clamp(h)

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        safe = _safe_visual_prompt(prompt, max_len=1800)
        negative = "text, letters, numbers, watermark, logo, typography, caption, words"
        w, h = self._snap_size(size)
        mid = self.model_id

        try:
            client = _bedrock_runtime_client()
            if mid in ("bedrock-titan", "bedrock-nova-canvas"):
                body = {
                    "taskType": "TEXT_IMAGE",
                    "textToImageParams": {
                        "text": safe,
                        "negativeText": negative,
                    },
                    "imageGenerationConfig": {
                        "numberOfImages": 1,
                        "height": h,
                        "width": w,
                        "cfgScale": 8.0,
                        "quality": "standard",
                    },
                }
            elif mid == "bedrock-sdxl":
                # SDXL on Bedrock uses Stability request schema
                body = {
                    "text_prompts": [
                        {"text": safe, "weight": 1.0},
                        {"text": negative, "weight": -1.0},
                    ],
                    "cfg_scale": 7,
                    "steps": 30,
                    "width": min(w, 1536),
                    "height": min(h, 1024),
                    "style_preset": "photographic",
                }
            else:
                # Stable Image Core / Ultra style
                body = {
                    "prompt": safe,
                    "negative_prompt": negative,
                    "mode": "text-to-image",
                    "aspect_ratio": "3:2" if w >= h else ("2:3" if h > w else "1:1"),
                    "output_format": "png",
                }

            resp = client.invoke_model(
                modelId=self.bedrock_model,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            payload = json.loads(resp["body"].read())
            return self._decode_image_payload(payload)
        except AppError:
            raise
        except Exception as e:
            raise AppError(f"Bedrock image failed ({self.bedrock_model}): {e}", 502, "BEDROCK_IMAGE_ERROR")

    def _decode_image_payload(self, payload: dict) -> bytes:
        # Titan / Nova: images[0] base64
        images = payload.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, str):
                return base64.b64decode(first)
            if isinstance(first, dict) and first.get("base64"):
                return base64.b64decode(first["base64"])

        # SDXL: artifacts[0].base64
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, list) and artifacts:
            b64 = artifacts[0].get("base64")
            if b64:
                return base64.b64decode(b64)

        # Stable Image: image or images
        if payload.get("image"):
            return base64.b64decode(payload["image"])

        raise AppError(
            f"Bedrock image response missing image bytes: {str(payload)[:280]}",
            502,
            "BEDROCK_IMAGE_ERROR",
        )


class IdeogramImageProvider(ImageBackgroundProvider):
    model_id = "ideogram"

    def __init__(self):
        self.api_key = (os.environ.get("IDEOGRAM_API_KEY") or "").strip()
        if not self.api_key:
            raise AppError("IDEOGRAM_API_KEY missing", 500, "AI_CONFIG")

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        # Ideogram aspect ratios; landscape for LinkedIn
        w, h = _parse_wh(size)
        aspect = "ASPECT_16_9" if w > h else ("ASPECT_9_16" if h > w else "ASPECT_1_1")
        safe = _safe_visual_prompt(prompt, max_len=2000)
        headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}
        body = {
            "image_request": {
                "prompt": safe,
                "aspect_ratio": aspect,
                "model": os.environ.get("IDEOGRAM_MODEL", "V_2"),
                "magic_prompt_option": "AUTO",
            }
        }
        with httpx.Client(timeout=180.0) as client:
            r = client.post("https://api.ideogram.ai/generate", headers=headers, json=body)
            if r.status_code >= 400:
                raise AppError(
                    f"Ideogram failed ({r.status_code}): {r.text[:400]}",
                    502,
                    "IDEOGRAM_ERROR",
                )
            data = r.json()
            url = None
            try:
                url = data["data"][0]["url"]
            except Exception:
                pass
            if not url:
                raise AppError("Ideogram response missing image url", 502, "IDEOGRAM_ERROR")
            img = client.get(url, timeout=120.0)
            img.raise_for_status()
            return img.content


class RecraftImageProvider(ImageBackgroundProvider):
    model_id = "recraft"

    def __init__(self):
        self.api_key = (os.environ.get("RECRAFT_API_KEY") or "").strip()
        if not self.api_key:
            raise AppError("RECRAFT_API_KEY missing", 500, "AI_CONFIG")

    def generate_background(self, prompt: str, size: str = "1536x1024") -> bytes:
        w, h = _parse_wh(size)
        # Recraft common sizes
        if w > h:
            size_name = "1536x1024"
        elif h > w:
            size_name = "1024x1536"
        else:
            size_name = "1024x1024"
        safe = _safe_visual_prompt(prompt)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "prompt": safe,
            "size": size_name,
            "style": os.environ.get("RECRAFT_STYLE", "realistic_image"),
            "model": os.environ.get("RECRAFT_MODEL", "recraftv3"),
            "n": 1,
            "response_format": "b64_json",
        }
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                "https://external.api.recraft.ai/v1/images/generations",
                headers=headers,
                json=body,
            )
            if r.status_code >= 400:
                raise AppError(
                    f"Recraft failed ({r.status_code}): {r.text[:400]}",
                    502,
                    "RECRAFT_ERROR",
                )
            data = r.json()["data"][0]
            if data.get("b64_json"):
                return base64.b64decode(data["b64_json"])
            url = data.get("url")
            if url:
                img = client.get(url, timeout=120.0)
                img.raise_for_status()
                return img.content
            raise AppError("Recraft response missing image", 502, "RECRAFT_ERROR")


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
        id="bedrock-titan",
        label="Titan Image G2 (Bedrock)",
        provider="bedrock",
        native_text_quality="poor",
        best_for="AWS-native backgrounds; good LinkedIn landscape",
        supported_sizes=["1024x1024", "1536x1024", "1024x1536"],
        cost_hint="Bedrock Titan Image pricing; enable model access",
        available=False,
        env_key="BEDROCK_ENABLED",
    ),
    ImageModelInfo(
        id="bedrock-nova-canvas",
        label="Nova Canvas (Bedrock)",
        provider="bedrock",
        native_text_quality="fair",
        best_for="AWS Nova image gen; strong product/scene visuals",
        supported_sizes=["1024x1024", "1536x1024", "1024x1536"],
        cost_hint="Bedrock Nova Canvas pricing",
        available=False,
        env_key="BEDROCK_ENABLED",
    ),
    ImageModelInfo(
        id="bedrock-sdxl",
        label="Stable Diffusion XL (Bedrock)",
        provider="bedrock",
        native_text_quality="poor",
        best_for="Creative / illustrative scenes on AWS",
        supported_sizes=["1024x1024", "1536x640", "1152x896"],
        cost_hint="Bedrock Stability SDXL pricing",
        available=False,
        env_key="BEDROCK_ENABLED",
    ),
    ImageModelInfo(
        id="bedrock-stable-image",
        label="Stable Image Core (Bedrock)",
        provider="bedrock",
        native_text_quality="poor",
        best_for="Fast Stability images via Bedrock",
        supported_sizes=["1024x1024", "1536x1024"],
        cost_hint="Bedrock Stability Image Core pricing",
        available=False,
        env_key="BEDROCK_ENABLED",
    ),
    ImageModelInfo(
        id="ideogram",
        label="Ideogram",
        provider="ideogram",
        native_text_quality="best",
        best_for="Native on-image text (experimental mode)",
        supported_sizes=["1024x1024", "1536x1024"],
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
        supported_sizes=["1024x1024", "1536x1024", "1024x1536"],
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
    bedrock_ok = bedrock_image_configured()
    openai_ok = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    out = []
    for m in REGISTRY:
        if m.id == "stub":
            available = True
        elif m.provider == "openai":
            available = openai_ok
        elif m.provider == "bedrock":
            available = bedrock_ok
        elif m.env_key:
            available = bool((os.environ.get(m.env_key) or "").strip())
        else:
            available = m.available
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


def get_image_provider(
    model_id: Optional[str] = None, *, api_keys: dict | None = None
) -> ImageBackgroundProvider:
    mid = (model_id or os.environ.get("OPENAI_IMAGE_MODEL") or "gpt-image-1").strip()
    keys = api_keys or {}
    openai_override = (keys.get("OPENAI_API_KEY") or keys.get("openai_api_key") or "").strip() or None
    if mid == "stub" or (os.environ.get("AI_PROVIDER") or "").lower() == "stub":
        return StubImageProvider()
    if mid in ("gpt-image-1", "dall-e-3", "gpt-image-1-mini"):
        return OpenAIImageProvider(
            mid if mid != "gpt-image-1-mini" else "gpt-image-1",
            api_key=openai_override,
        )
    if mid.startswith("bedrock-"):
        return BedrockImageProvider(mid)
    if mid == "ideogram":
        if (os.environ.get("IDEOGRAM_API_KEY") or "").strip():
            return IdeogramImageProvider()
        return MissingKeyImageProvider("ideogram", "IDEOGRAM_API_KEY")
    if mid == "recraft":
        if (os.environ.get("RECRAFT_API_KEY") or "").strip():
            return RecraftImageProvider()
        return MissingKeyImageProvider("recraft", "RECRAFT_API_KEY")
    # Default OpenAI
    return OpenAIImageProvider(
        os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        api_key=openai_override,
    )


def nearest_gen_size(preset_w: int, preset_h: int, model_id: str) -> str:
    """Map LinkedIn preset to a provider-supported generation size."""
    ratio = preset_w / max(preset_h, 1)
    if model_id.startswith("dall-e"):
        if ratio > 1.2:
            return "1792x1024"
        if ratio < 0.85:
            return "1024x1792"
        return "1024x1024"
    if model_id.startswith("bedrock-sdxl"):
        if ratio > 1.2:
            return "1536x640"
        if ratio < 0.85:
            return "896x1152"
        return "1024x1024"
    # gpt-image, titan, nova, ideogram, recraft — landscape LinkedIn default
    if ratio > 1.2:
        return "1536x1024"
    if ratio < 0.85:
        return "1024x1536"
    return "1024x1024"
