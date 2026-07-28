from __future__ import annotations
from typing import Any, Callable

class RouteRegistry:
    def __init__(self):
        self._controllers: list[type] = []
        self._routes: list[dict[str, Any]] = []

    def register_controller(self, cls: type):
        if cls not in self._controllers:
            self._controllers.append(cls)
            for route in getattr(cls, "__routes__", []):
                self._routes.append({**route, "controller": cls})

    def get_routes(self, lambda_name: str | None = None) -> list[dict[str, Any]]:
        routes = []
        for cls in self._controllers:
            meta = getattr(cls, "__controller_meta__", {})
            if lambda_name and meta.get("lambda_name") and meta["lambda_name"] != lambda_name:
                continue
            for route in getattr(cls, "__routes__", []):
                routes.append({**route, "controller": cls, "base_path": meta.get("path", "")})
        return routes

    def all_controllers(self) -> list[type]:
        return list(self._controllers)

route_registry = RouteRegistry()
