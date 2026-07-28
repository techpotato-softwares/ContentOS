import re

def match(full: str, path: str):
    pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", full)
    m = re.match(f"^{pattern}$", path)
    return m.groupdict() if m else None

def test_path_params():
    assert match("/api/demo/items/{id}", "/api/demo/items/12") == {"id": "12"}
    assert match("/api/demo/items", "/api/demo/items") == {}
