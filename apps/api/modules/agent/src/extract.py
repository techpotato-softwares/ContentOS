"""Extract text from URLs and PDFs for repurposing into LinkedIn briefs."""
from __future__ import annotations
import base64
import io
import re
from html import unescape
from urllib.parse import urlparse
import httpx
from middleware.error_handler import ValidationError, AppError


MAX_CHARS = 12000
USER_AGENT = (
    "ContentOSBot/1.0 (+https://contentos.app; repurpose extractor; contact=support)"
)


def _clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_from_url(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        raise ValidationError("url is required")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError("url must be a valid http(s) URL")

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": USER_AGENT})
            if r.status_code >= 400:
                raise AppError(
                    f"Failed to fetch URL ({r.status_code})",
                    502,
                    "URL_FETCH_ERROR",
                )
            ctype = (r.headers.get("content-type") or "").lower()
            if "pdf" in ctype or url.lower().endswith(".pdf"):
                return extract_from_pdf_bytes(r.content, source=url)
            html = r.text
    except AppError:
        raise
    except Exception as e:
        raise AppError(f"URL fetch error: {e}", 502, "URL_FETCH_ERROR")

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = _clean_text(re.sub(r"<[^>]+>", "", m.group(1)))[:200]

    # Drop scripts/styles then strip tags
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = _clean_text(text)
    if len(text) < 80:
        raise ValidationError("Could not extract enough readable text from that URL")
    text = text[:MAX_CHARS]
    brief = _brief_from_source(title or parsed.netloc, text, source_kind="web page")
    return {
        "sourceType": "url",
        "sourceRef": url,
        "title": title or parsed.netloc,
        "text": text,
        "charCount": len(text),
        "brief": brief,
    }


def extract_from_pdf_bytes(data: bytes, source: str = "upload.pdf") -> dict:
    if not data:
        raise ValidationError("PDF content is empty")
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise AppError(
            "pypdf is not installed. Run: pip install pypdf",
            500,
            "PDF_DEP_MISSING",
        ) from e

    try:
        reader = PdfReader(io.BytesIO(data))
        parts: list[str] = []
        for page in reader.pages[:40]:
            parts.append(page.extract_text() or "")
        text = _clean_text("\n".join(parts))
    except Exception as e:
        raise AppError(f"PDF parse error: {e}", 400, "PDF_PARSE_ERROR")

    if len(text) < 80:
        raise ValidationError("Could not extract enough text from that PDF")
    text = text[:MAX_CHARS]
    title = source.rsplit("/", 1)[-1] if source else "Uploaded PDF"
    brief = _brief_from_source(title, text, source_kind="PDF document")
    return {
        "sourceType": "pdf",
        "sourceRef": source,
        "title": title,
        "text": text,
        "charCount": len(text),
        "brief": brief,
    }


def extract_from_pdf_base64(pdf_b64: str, filename: str | None = None) -> dict:
    raw = (pdf_b64 or "").strip()
    if not raw:
        raise ValidationError("pdfBase64 is required")
    if "," in raw and raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as e:
        raise ValidationError(f"Invalid pdfBase64: {e}")
    if len(data) > 12 * 1024 * 1024:
        raise ValidationError("PDF must be under 12MB")
    return extract_from_pdf_bytes(data, source=filename or "upload.pdf")


def _brief_from_source(title: str, text: str, source_kind: str) -> str:
    excerpt = text[:3500]
    return (
        f"Repurpose this {source_kind} into an informative branded LinkedIn image post "
        f"for our company audience.\n\n"
        f"Title: {title}\n\n"
        f"Source excerpt:\n{excerpt}\n\n"
        "Extract 1–2 practical insights, keep claims faithful to the source, "
        "and write a strong CTA aligned with our brand voice."
    )
