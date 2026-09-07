"""Publish approved posts whose scheduled_at is due."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "layers" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT))

from sqlmodel import select
from database import get_session
from database.models import ContentPost
from utils.logger import logger
from utils.tenant import write_audit


def handler(event, context):
    """Rate: every 15 minutes — publish due scheduled posts that are approved."""
    now = datetime.utcnow()
    published = []
    errors = []
    with get_session() as session:
        due = session.exec(
            select(ContentPost).where(
                ContentPost.status == "approved",
                ContentPost.scheduled_at != None,  # noqa: E711
                ContentPost.scheduled_at <= now,
            )
        ).all()
        for post in due:
            try:
                from modules.publishing.src.controllers.publishing_controller import (
                    _load_tokens,
                    _pick_publish_account,
                    _ensure_social_account_columns,
                )
                from modules.publishing.src.linkedin_client import execute_linkedin_publish

                _ensure_social_account_columns()
                acct, kind = _pick_publish_account(session, post.tenant_id, None)
                layout = None
                if post.layout_json:
                    try:
                        layout = json.loads(post.layout_json)
                    except Exception:
                        layout = None
                fmt = (layout or {}).get("format") or ("text" if not post.image_url else "image")

                if not acct or not acct.token_payload_encrypted or not acct.author_urn:
                    raise RuntimeError("LinkedIn account not ready for scheduled publish")

                tokens = _load_tokens(acct)
                access = tokens.get("access_token") or ""
                allow_stub = os.environ.get("IS_LOCAL") == "true" and not os.environ.get(
                    "LINKEDIN_CLIENT_ID"
                )
                linkedin_id = execute_linkedin_publish(
                    access_token=access,
                    author_urn=acct.author_urn,
                    caption=post.caption or "",
                    image_url=post.image_url,
                    layout=layout,
                    allow_stub=allow_stub,
                )

                post.status = "published"
                post.linkedin_post_id = linkedin_id
                post.published_at = now
                post.updated_at = now
                session.add(post)
                write_audit(
                    session,
                    tenant_id=post.tenant_id,
                    actor_user_id=post.user_id,
                    action="posts.scheduled_publish",
                    resource_type="content_post",
                    resource_id=str(post.post_id),
                    detail=json.dumps(
                        {"linkedinId": linkedin_id, "publishAs": kind, "format": fmt}
                    ),
                )
                published.append(post.post_id)
                logger.info("scheduled publish ok", {"postId": post.post_id})
            except Exception as e:
                errors.append({"postId": post.post_id, "error": str(e)})
                logger.error(
                    "scheduled publish failed",
                    {"postId": post.post_id, "error": str(e)},
                )
        session.commit()
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"published": published, "errors": errors, "checkedAt": now.isoformat() + "Z"}
        ),
    }
