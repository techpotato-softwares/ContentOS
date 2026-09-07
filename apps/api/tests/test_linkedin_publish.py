"""LinkedIn publishing hardening — personal UGC, org posts, errors, carousel flag."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "layers/shared/python/src"))
sys.path.insert(0, str(ROOT))

from middleware.error_handler import AppError
from modules.publishing.src.linkedin_client import (
    carousel_capability,
    execute_linkedin_publish,
    linkedin_ugc_publish,
    map_linkedin_http_error,
)


def test_map_expired_token_to_reconnect():
    err = map_linkedin_http_error(401, '{"message":"REVOKED_ACCESS_TOKEN"}')
    assert err.code == "LINKEDIN_RECONNECT_REQUIRED"
    assert "Reconnect" in err.message


def test_map_scope_missing():
    err = map_linkedin_http_error(403, "Not enough permissions to access scope w_organization_social")
    assert err.code == "LINKEDIN_SCOPE_MISSING"


def test_map_unsupported_media():
    err = map_linkedin_http_error(400, "Unsupported media type for this share")
    assert err.code == "LINKEDIN_MEDIA_UNSUPPORTED"


def test_carousel_disabled_flag(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CAROUSEL_ENABLED", "false")
    cap = carousel_capability()
    assert cap["enabled"] is False
    with pytest.raises(AppError) as exc:
        execute_linkedin_publish(
            access_token="tok",
            author_urn="urn:li:person:abc",
            caption="hi",
            image_url=None,
            layout={
                "format": "carousel",
                "slides": [{"imageUrl": "https://example.com/a.png"}],
            },
            allow_stub=False,
        )
    assert exc.value.code == "LINKEDIN_CAROUSEL_DISABLED"


def test_personal_text_and_image_ugc_publish(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test-client")
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    class FakeResp:
        def __init__(self, status_code=200, payload=None, headers=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}
            self.text = text or json.dumps(self._payload)
            self.content = tiny_png

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.text)

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kwargs):
            return FakeResp(200)

        def post(self, url, **kwargs):
            if "registerUpload" in url:
                return FakeResp(
                    200,
                    {
                        "value": {
                            "asset": "urn:li:digitalmediaAsset:IMG1",
                            "uploadMechanism": {
                                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {
                                    "uploadUrl": "https://upload.example/put"
                                }
                            },
                        }
                    },
                )
            if "ugcPosts" in url:
                body = kwargs.get("json") or {}
                author = body.get("author")
                assert author == "urn:li:person:member1"
                share = body["specificContent"]["com.linkedin.ugc.ShareContent"]
                assert share["shareMediaCategory"] == "IMAGE"
                assert "hello personal" in share["shareCommentary"]["text"]
                return FakeResp(201, {"id": "urn:li:share:personal-1"}, {"x-restli-id": "urn:li:share:personal-1"})
            return FakeResp(404, text="unexpected")

        def put(self, url, **kwargs):
            return FakeResp(201)

    with patch("modules.publishing.src.linkedin_client.httpx.Client", FakeClient):
        post_id = linkedin_ugc_publish(
            "access-token",
            "urn:li:person:member1",
            "hello personal",
            "https://cdn.example.com/post.png",
        )
    assert post_id == "urn:li:share:personal-1"


def test_company_page_ugc_publish_uses_org_urn(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test-client")

    class FakeResp:
        def __init__(self, status_code=200, payload=None, headers=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.headers = headers or {}
            self.text = text or json.dumps(self._payload)

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, **kwargs):
            assert "ugcPosts" in url
            body = kwargs.get("json") or {}
            assert body["author"] == "urn:li:organization:999"
            share = body["specificContent"]["com.linkedin.ugc.ShareContent"]
            assert share["shareMediaCategory"] == "NONE"
            return FakeResp(201, headers={"x-restli-id": "urn:li:share:org-1"})

    with patch("modules.publishing.src.linkedin_client.httpx.Client", FakeClient):
        post_id = linkedin_ugc_publish(
            "access-token",
            "urn:li:organization:999",
            "company update",
            None,
        )
    assert post_id == "urn:li:share:org-1"


def test_execute_publish_personal_image_via_shared_path(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test-client")

    with patch(
        "modules.publishing.src.linkedin_client.linkedin_ugc_publish",
        return_value="urn:li:share:x",
    ) as ugc:
        out = execute_linkedin_publish(
            access_token="t",
            author_urn="urn:li:person:1",
            caption="cap",
            image_url="https://example.com/a.png",
            layout={"format": "image"},
            allow_stub=False,
        )
    assert out == "urn:li:share:x"
    ugc.assert_called_once()
    assert ugc.call_args[0][3] == "https://example.com/a.png"


def test_scheduled_publisher_uses_execute_linkedin_publish(monkeypatch):
    monkeypatch.setenv("LINKEDIN_CLIENT_ID", "test-client")
    monkeypatch.delenv("IS_LOCAL", raising=False)

    from datetime import datetime, timedelta

    post = MagicMock()
    post.post_id = 42
    post.tenant_id = 7
    post.user_id = 3
    post.status = "approved"
    post.scheduled_at = datetime.utcnow() - timedelta(minutes=5)
    post.layout_json = json.dumps({"format": "text"})
    post.image_url = None
    post.caption = "scheduled hello"
    post.linkedin_post_id = None

    acct = MagicMock()
    acct.token_payload_encrypted = "x"
    acct.author_urn = "urn:li:person:1"

    session = MagicMock()
    session.exec.return_value.all.return_value = [post]
    session_cm = MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False

    with (
        patch("database.get_session", return_value=session_cm),
        patch(
            "modules.publishing.src.controllers.publishing_controller._ensure_social_account_columns"
        ),
        patch(
            "modules.publishing.src.controllers.publishing_controller._pick_publish_account",
            return_value=(acct, "member"),
        ),
        patch(
            "modules.publishing.src.controllers.publishing_controller._load_tokens",
            return_value={"access_token": "tok"},
        ),
        patch(
            "modules.publishing.src.linkedin_client.execute_linkedin_publish",
            return_value="urn:li:share:sched",
        ) as exec_pub,
        patch("utils.tenant.write_audit"),
    ):
        from src.lambdas.scheduled_publisher import handler

        result = handler({}, None)

    body = json.loads(result["body"])
    assert body["published"] == [42]
    assert body["errors"] == []
    assert post.status == "published"
    assert post.linkedin_post_id == "urn:li:share:sched"
    exec_pub.assert_called_once()
    assert exec_pub.call_args.kwargs["author_urn"] == "urn:li:person:1"
    assert exec_pub.call_args.kwargs["caption"] == "scheduled hello"
