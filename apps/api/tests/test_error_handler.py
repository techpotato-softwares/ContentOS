import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "layers/shared/python/src"))

from middleware.error_handler import ForbiddenError, ConflictError, create_error_response
import json

def test_forbidden():
    err = ForbiddenError("nope")
    assert err.status_code == 403
    resp = create_error_response(err)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "FORBIDDEN"


def test_conflict_409():
    err = ConflictError("An account with this email already exists.")
    assert err.status_code == 409
    resp = create_error_response(err)
    assert resp["statusCode"] == 409
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "CONFLICT"
    assert "email" in body["error"]["message"].lower()
    assert "Traceback" not in body["error"]["message"]

