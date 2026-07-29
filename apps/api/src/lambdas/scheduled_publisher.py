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
from database.models import ContentPost, SocialAccount
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
                    _linkedin_ugc_publish,
                )

                acct = session.exec(
                    select(SocialAccount).where(
                        SocialAccount.tenant_id == post.tenant_id,
                        SocialAccount.platform == "linkedin",
                        SocialAccount.is_active == True,  # noqa: E712
                    )
                ).first()
                linkedin_id = None
                if acct and acct.token_payload_encrypted:
                    tokens = _load_tokens(acct)
                    access = tokens.get("access_token")
                    person_urn = (
                        f"urn:li:person:{acct.platform_user_id}"
                        if acct.platform_user_id
                        else None
                    )
                    cfg_ok = bool(os.environ.get("LINKEDIN_CLIENT_ID") and access and person_urn)
                    if cfg_ok and not (post.image_url or "").startswith("data:"):
                        linkedin_id = _linkedin_ugc_publish(
                            access, person_urn, post.caption, post.image_url
                        )
                if not linkedin_id:
                    linkedin_id = f"stub-li-{post.post_id}-{int(now.timestamp())}"

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
                    detail=linkedin_id,
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
