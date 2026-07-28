from __future__ import annotations

def _method(method: str):
    def factory(path: str = "/"):
        def deco(fn):
            pending = getattr(fn, "__route_pending__", {})
            defs = getattr(fn, "__route_defs__", [])
            defs.append({"method": method, "path": path, "handler": fn.__name__, **pending})
            fn.__route_defs__ = defs
            return fn
        return deco
    return factory

Get = _method("GET")
Post = _method("POST")
Put = _method("PUT")
Delete = _method("DELETE")
Patch = _method("PATCH")
