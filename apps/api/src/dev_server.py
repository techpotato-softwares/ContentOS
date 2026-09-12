"""
FastAPI local development server for ContentOS API.
Wraps the same Lambda handlers used in AWS.

From apps/api/:
  uvicorn src.dev_server:app --reload --port 4001
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("IS_LOCAL", "true")
os.environ.setdefault("APP_NAME", "contentos")

# Load .env (overwrite so local keys always win over empty shell exports)
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ[k] = v

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import modules.platform.lambdas.auth  # noqa: F401
import modules.tenants.lambdas.tenants  # noqa: F401
import modules.agent.lambdas.agent  # noqa: F401
import modules.publishing.lambdas.publishing  # noqa: F401

from modules.platform.lambdas.auth import handler as auth_handler
from modules.tenants.lambdas.tenants import handler as tenants_handler
from modules.agent.lambdas.agent import handler as agent_handler
from modules.publishing.lambdas.publishing import handler as publishing_handler

HANDLERS = {
    "auth": auth_handler,
    "tenants": tenants_handler,
    "agent": agent_handler,
    "publishing": publishing_handler,
}

ROUTE_MAP = [
    ("/api/login", "auth"),
    ("/api/auth", "auth"),
    ("/api/register", "auth"),
    ("/api/me", "auth"),
    ("/api/admin/tenants", "tenants"),
    ("/api/tenants", "tenants"),
    ("/api/agent", "agent"),
    ("/api/social", "publishing"),
    ("/api/posts", "publishing"),
]

app = FastAPI(title="ContentOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local generated images
_media = ROOT / "media"
_media.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_media)), name="media")


def pick_handler(path: str):
    # Longest prefix match
    best = None
    best_len = -1
    for prefix, name in ROUTE_MAP:
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix):
            if len(prefix) > best_len:
                best = name
                best_len = len(prefix)
    return HANDLERS.get(best or "auth", auth_handler)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "product": "contentos",
        "aiProvider": os.environ.get("AI_PROVIDER", "openai"),
        "openaiKeyConfigured": bool((os.environ.get("OPENAI_API_KEY") or "").strip()),
    }


@app.get("/dev/mailbox")
def dev_mailbox():
    """Local OTP inbox UI (IS_LOCAL only)."""
    if os.environ.get("IS_LOCAL") != "true":
        return Response(content="Not available", status_code=404)
    from utils.local_mailbox import extract_otp_codes, list_messages
    from html import escape

    messages = list_messages(40)
    cards = []
    for m in messages:
        text = m.get("text") or ""
        codes = extract_otp_codes(text)
        code_html = (
            f"<p style='font-size:28px;letter-spacing:4px;font-weight:700'>{escape(codes[0])}</p>"
            if codes
            else ""
        )
        cards.append(
            "<article style='border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0'>"
            f"<div style='color:#666;font-size:12px'>{escape(m.get('createdAt') or '')}</div>"
            f"<div><strong>To:</strong> {escape(', '.join(m.get('to') or []))}</div>"
            f"<div><strong>Subject:</strong> {escape(m.get('subject') or '')}</div>"
            f"{code_html}"
            f"<pre style='white-space:pre-wrap;background:#f6f6f6;padding:12px;border-radius:8px'>"
            f"{escape(text)}</pre>"
            "</article>"
        )
    body = f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>ContentOS local mailbox</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px}}
a{{color:#0d9488}}</style></head>
<body>
<h1>Local OTP mailbox</h1>
<p>Emails are saved here when <code>EMAIL_TRANSPORT=local</code> (or SES/SMTP unavailable locally).
Refresh after requesting an OTP. Login: <a href="http://127.0.0.1:5173/login">web app</a></p>
{''.join(cards) if cards else '<p>No messages yet. Request an OTP from the login page.</p>'}
</body></html>"""
    return Response(content=body, media_type="text/html")


@app.get("/dev/mailbox.json")
def dev_mailbox_json():
    if os.environ.get("IS_LOCAL") != "true":
        return {"error": "Not available"}
    from utils.local_mailbox import list_messages

    return {"messages": list_messages(40)}


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def catch_all(request: Request, full_path: str):
    path = "/" + full_path
    body = await request.body()
    event = {
        "httpMethod": request.method,
        "path": path,
        "headers": dict(request.headers),
        "queryStringParameters": dict(request.query_params) or None,
        "body": body.decode("utf-8") if body else None,
        "isBase64Encoded": False,
    }
    result = pick_handler(path)(event, None)
    headers = result.get("headers") or {"Content-Type": "application/json"}
    if result.get("statusCode") in (301, 302) and headers.get("Location"):
        return Response(
            content="",
            status_code=result["statusCode"],
            headers=headers,
        )
    return Response(
        content=result.get("body") or "",
        status_code=result.get("statusCode", 200),
        headers=headers,
        media_type="application/json",
    )
