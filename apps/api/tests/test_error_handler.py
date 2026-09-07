import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "layers/shared/python/src"))

from middleware.error_handler import ForbiddenError, RateLimitError, create_error_response
import json

def test_forbidden():
    err = ForbiddenError("nope")
    assert err.status_code == 403
    resp = create_error_response(err)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "FORBIDDEN"


def test_rate_limited():
    err = RateLimitError("slow down")
    assert err.status_code == 429
    resp = create_error_response(err)
    assert resp["statusCode"] == 429
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "RATE_LIMITED"
    assert resp["headers"]["Retry-After"] == "60"
