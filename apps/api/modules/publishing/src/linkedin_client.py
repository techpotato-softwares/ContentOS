"""LinkedIn UGC / documents client + actionable error mapping for Review UI."""
from __future__ import annotations

import base64
import io
import os
from typing import Any

import httpx

from middleware.error_handler import AppError


def carousel_publishing_enabled() -> bool:
    """Feature flag — set LINKEDIN_CAROUSEL_ENABLED=false to disable with a clear UI message."""
    raw = (os.environ.get("LINKEDIN_CAROUSEL_ENABLED") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def map_linkedin_http_error(
    status: int,
    body: str,
    *,
    default_code: str = "LINKEDIN_ERROR",
    context: str = "publish",
) -> AppError:
    """Turn LinkedIn API failures into clear, actionable AppErrors for the Review UI."""
    text = (body or "")[:600]
    lower = text.lower()

    if status in (401, 403) or "revoked_access_token" in lower or "expired" in lower:
        if "scope" in lower or "insufficient" in lower or "not enough permissions" in lower:
            return AppError(
                "LinkedIn permission missing for this action. Reconnect LinkedIn and approve "
                "all requested scopes (personal: w_member_social; company: "
                "w_organization_social + r_organization_admin).",
                403,
                "LINKEDIN_SCOPE_MISSING",
            )
        return AppError(
            "LinkedIn session expired or was revoked. Reconnect your account under Connections → LinkedIn.",
            401,
            "LINKEDIN_RECONNECT_REQUIRED",
        )

    if status == 429 or "throttle" in lower or "rate limit" in lower:
        return AppError(
            "LinkedIn rate-limited this request. Wait a few minutes and try again.",
            429,
            "LINKEDIN_RATE_LIMITED",
        )

    if (
        "unsupported" in lower
        or "media type" in lower
        or "invalid media" in lower
        or "contenttype" in lower
        or "content-type" in lower
    ):
        return AppError(
            "LinkedIn rejected this media. Use a JPEG/PNG image under LinkedIn size limits, "
            "or for carousels a multi-page PDF document.",
            400,
            "LINKEDIN_MEDIA_UNSUPPORTED",
        )

    if "organization" in lower and (
        "acl" in lower or "permission" in lower or "not authorized" in lower
    ):
        return AppError(
            "Not allowed to post as this company page. Reconnect the page as an admin with "
            "posting rights, then select the page again.",
            403,
            "LINKEDIN_ORG_FORBIDDEN",
        )

    if "document" in lower or context == "carousel":
        return AppError(
            "LinkedIn document/carousel publish failed. Ensure Documents API access is enabled "
            f"on your LinkedIn app, or switch the post to image/text. Details: {text[:200]}",
            502,
            "LINKEDIN_CAROUSEL_UNAVAILABLE",
        )

    return AppError(
        f"LinkedIn {context} failed ({status}): {text[:280]}",
        502,
        default_code,
    )


def _fetch_image_bytes(url: str) -> bytes | None:
    if not url:
        return None
    if url.startswith("data:"):
        try:
            _, b64 = url.split(",", 1)
            return base64.b64decode(b64)
        except Exception:
            return None
    if url.startswith("/media/"):
        from pathlib import Path

        # modules/publishing/src/linkedin_client.py → parents[3]=apps/api
        media_root = Path(__file__).resolve().parents[3] / "media"
        local = media_root / url[len("/media/") :]
        if local.exists():
            return local.read_bytes()
        return None
    if url.startswith("http://") or url.startswith("https://"):
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.get(url)
                if r.status_code == 200:
                    return r.content
        except Exception:
            return None
    return None


def _register_linkedin_image(
    client: httpx.Client, access_token: str, author_urn: str, image_bytes: bytes
) -> str:
    """Register + upload image asset; raise actionable AppError on failure."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    register = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": author_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }
    reg = client.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json=register,
    )
    if reg.status_code >= 400:
        raise map_linkedin_http_error(
            reg.status_code, reg.text, default_code="LINKEDIN_MEDIA_UNSUPPORTED", context="image upload"
        )
    value = (reg.json() or {}).get("value") or {}
    asset = value.get("asset")
    upload_mech = (
        (value.get("uploadMechanism") or {})
        .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest")
        or {}
    )
    upload_url = upload_mech.get("uploadUrl")
    if not asset or not upload_url:
        raise AppError(
            "LinkedIn image upload could not be initialized. Reconnect LinkedIn and retry.",
            502,
            "LINKEDIN_MEDIA_UNSUPPORTED",
        )
    up = client.put(
        upload_url,
        content=image_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
        },
    )
    if up.status_code >= 400:
        raise map_linkedin_http_error(
            up.status_code, up.text, default_code="LINKEDIN_MEDIA_UNSUPPORTED", context="image upload"
        )
    return asset


def linkedin_ugc_publish(
    access_token: str, author_urn: str, caption: str, image_url: str | None
) -> str:
    """Publish text (and optional image) via LinkedIn ugcPosts for person or organization URN."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    share_content: dict[str, Any] = {
        "shareCommentary": {"text": (caption or "")[:2900]},
        "shareMediaCategory": "NONE",
    }
    with httpx.Client(timeout=120.0) as client:
        if image_url:
            raw = _fetch_image_bytes(image_url)
            if not raw:
                raise AppError(
                    "Could not load the post image for LinkedIn. Re-generate the image or use a public HTTPS URL.",
                    400,
                    "LINKEDIN_MEDIA_UNSUPPORTED",
                )
            asset = _register_linkedin_image(client, access_token, author_urn, raw)
            share_content = {
                "shareCommentary": {"text": (caption or "")[:2900]},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "description": {"text": "Image"},
                        "media": asset,
                        "title": {"text": "Image"},
                    }
                ],
            }
        share = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        r = client.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=share)
        if r.status_code >= 400:
            raise map_linkedin_http_error(r.status_code, r.text, context="publish")
        return r.headers.get("x-restli-id") or (r.json() or {}).get("id") or r.text[:80]


def _slide_images_to_pdf(slide_urls: list[str]) -> bytes:
    from PIL import Image

    images = []
    for url in slide_urls:
        raw = _fetch_image_bytes(url)
        if not raw:
            continue
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        images.append(im)
    if not images:
        raise AppError(
            "Could not load carousel slide images for PDF. Ensure each slide has a reachable imageUrl.",
            400,
            "CAROUSEL_EMPTY",
        )
    buf = io.BytesIO()
    first, rest = images[0], images[1:]
    first.save(buf, format="PDF", save_all=True, append_images=rest)
    return buf.getvalue()


def linkedin_document_publish(
    access_token: str, author_urn: str, caption: str, slide_urls: list[str]
) -> str:
    """Stitch slide images into a PDF and publish as a LinkedIn document (native carousel UX)."""
    if not carousel_publishing_enabled():
        raise AppError(
            "Carousel publishing is disabled. Switch this post to image or text, or ask an admin "
            "to enable LINKEDIN_CAROUSEL_ENABLED after Documents API access is approved.",
            400,
            "LINKEDIN_CAROUSEL_DISABLED",
        )

    pdf_bytes = _slide_images_to_pdf(slide_urls)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": os.environ.get("LINKEDIN_API_VERSION", "202506"),
    }
    register_body = {
        "initializeUploadRequest": {
            "owner": author_urn,
            "fileSizeBytes": len(pdf_bytes),
        }
    }
    with httpx.Client(timeout=120.0) as client:
        reg = client.post(
            "https://api.linkedin.com/rest/documents?action=initializeUpload",
            headers=headers,
            json=register_body,
        )
        if reg.status_code >= 400:
            raise map_linkedin_http_error(
                reg.status_code,
                reg.text,
                default_code="LINKEDIN_CAROUSEL_UNAVAILABLE",
                context="carousel",
            )
        value = (reg.json() or {}).get("value") or {}
        upload_url = value.get("uploadUrl")
        document_urn = value.get("document")
        if not upload_url or not document_urn:
            raise AppError(
                "LinkedIn document upload did not return uploadUrl. Confirm Documents API product "
                "access on the LinkedIn developer app.",
                502,
                "LINKEDIN_CAROUSEL_UNAVAILABLE",
            )
        up = client.put(
            upload_url,
            content=pdf_bytes,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/pdf",
            },
        )
        if up.status_code >= 400:
            raise map_linkedin_http_error(
                up.status_code,
                up.text,
                default_code="LINKEDIN_CAROUSEL_UNAVAILABLE",
                context="carousel",
            )

        post_body = {
            "author": author_urn,
            "commentary": (caption or "")[:3000],
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": {"id": document_urn}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        pr = client.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json=post_body,
        )
        if pr.status_code < 400:
            return pr.headers.get("x-restli-id") or (pr.json() or {}).get("id") or document_urn

        # Fallback: UGC share referencing the document URN
        ugc = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": (caption or "")[:2900]},
                    "shareMediaCategory": "DOCUMENT",
                    "media": [
                        {
                            "status": "READY",
                            "media": document_urn,
                            "title": {"text": "Carousel"},
                        }
                    ],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        ugc_r = client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=ugc,
        )
        if ugc_r.status_code >= 400:
            raise map_linkedin_http_error(
                ugc_r.status_code,
                f"{pr.text[:200]} | {ugc_r.text[:200]}",
                default_code="LINKEDIN_CAROUSEL_UNAVAILABLE",
                context="carousel",
            )
        return ugc_r.headers.get("x-restli-id") or (ugc_r.json() or {}).get("id") or ugc_r.text[:80]


def post_format(layout: dict | None, image_url: str | None) -> str:
    if layout and layout.get("format"):
        return str(layout["format"])
    return "text" if not image_url else "image"


def image_url_for_share(fmt: str, image_url: str | None) -> str | None:
    if not image_url:
        return None
    if fmt in ("text", "image"):
        return image_url
    return None


def execute_linkedin_publish(
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    image_url: str | None,
    layout: dict | None,
    allow_stub: bool = False,
) -> str:
    """
    Shared publish path for HTTP publish + scheduled_publisher.
    When LinkedIn is not configured and allow_stub=True, returns a stub id (local/dev only).
    """
    fmt = post_format(layout, image_url)
    cfg_ok = bool(os.environ.get("LINKEDIN_CLIENT_ID") and access_token and author_urn)

    if fmt == "carousel":
        if not carousel_publishing_enabled():
            raise AppError(
                "Carousel publishing is disabled for this environment. Convert to image/text "
                "or enable LINKEDIN_CAROUSEL_ENABLED after Documents API approval. "
                "Ticket note: carousel uses PDF document upload via /rest/documents.",
                400,
                "LINKEDIN_CAROUSEL_DISABLED",
            )
        slides = (layout or {}).get("slides") or []
        slide_urls = [
            s.get("imageUrl") for s in slides if isinstance(s, dict) and s.get("imageUrl")
        ]
        if not slide_urls:
            raise AppError(
                "Carousel has no slide images to publish",
                400,
                "CAROUSEL_EMPTY",
            )
        if not cfg_ok:
            if allow_stub:
                return f"stub-carousel-{int(__import__('time').time())}"
            raise AppError(
                "LinkedIn is not configured for document carousel publish",
                400,
                "LINKEDIN_CAROUSEL_UNAVAILABLE",
            )
        return linkedin_document_publish(access_token, author_urn, caption, slide_urls)

    if not cfg_ok:
        if allow_stub:
            return f"stub-li-{int(__import__('time').time())}"
        raise AppError(
            "LinkedIn is not connected or LINKEDIN_CLIENT_ID is missing. Connect under Connections → LinkedIn.",
            400,
            "LINKEDIN_DISCONNECTED",
        )

    return linkedin_ugc_publish(
        access_token,
        author_urn,
        caption,
        image_url_for_share(fmt, image_url),
    )


def carousel_capability() -> dict[str, Any]:
    return {
        "enabled": carousel_publishing_enabled(),
        "mode": "pdf_document",
        "message": (
            "Carousels publish as a LinkedIn multi-page PDF document (Documents API)."
            if carousel_publishing_enabled()
            else "Carousel publishing is disabled. Use image or text posts, or enable LINKEDIN_CAROUSEL_ENABLED."
        ),
    }
