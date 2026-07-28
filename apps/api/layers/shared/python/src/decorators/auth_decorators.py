from __future__ import annotations

def _pending(fn, **kwargs):
    pending = getattr(fn, "__route_pending__", {})
    pending.update(kwargs)
    fn.__route_pending__ = pending
    # also merge into existing route defs
    for r in getattr(fn, "__route_defs__", []):
        r.update(kwargs)
    return fn

def ApiPublic():
    def deco(fn):
        return _pending(fn, public=True)
    return deco

def RequirePermission(*codes: str):
    def deco(fn):
        return _pending(fn, permissions=list(codes))
    return deco

def RequireModule(sku: str):
    def deco(fn):
        return _pending(fn, required_module=sku)
    return deco
