from __future__ import annotations
from decorators.registry import route_registry

def Controller(path: str = "/", lambda_name: str | None = None):
    def deco(cls):
        cls.__controller_meta__ = {"path": path.rstrip("/") or "/", "lambda_name": lambda_name}
        routes = []
        for name, attr in list(cls.__dict__.items()):
            if callable(attr) and hasattr(attr, "__route_defs__"):
                for r in attr.__route_defs__:
                    routes.append({**r, "method_name": name, "fn": attr})
        cls.__routes__ = routes
        route_registry.register_controller(cls)
        return cls
    return deco
