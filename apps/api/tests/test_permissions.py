def has_permission(owned, required=None):
    if not required:
        return True
    s = set(owned or [])
    return any(c in s for c in required)

def test_permission_any_of():
    assert has_permission(["demo:write"], ["demo:write", "admin"])
    assert has_permission(["admin"], ["demo:write", "admin"])
    assert not has_permission(["demo:read"], ["demo:write", "admin"])
