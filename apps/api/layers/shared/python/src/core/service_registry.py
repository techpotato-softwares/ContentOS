from __future__ import annotations
from typing import Any, Callable
from utils.logger import logger

class LambdaRegistry:
    def __init__(self):
        self._defs: dict[str, dict[str, Any]] = {}
        self._containers: dict[str, dict[str, Any]] = {}

    def define(self, name: str, controllers: list[type], bindings: list[dict] | None = None):
        self._defs[name] = {"controllers": controllers, "bindings": bindings or []}

    def get_container(self, name: str) -> dict[str, Any]:
        if name in self._containers:
            return self._containers[name]
        definition = self._defs.get(name)
        if not definition:
            raise RuntimeError(f"Lambda '{name}' not defined")
        container: dict[str, Any] = {"controllers": {}}
        # instantiate controllers with no-arg or simple DI later
        for ctrl in definition["controllers"]:
            container["controllers"][ctrl] = ctrl()
        self._containers[name] = container
        logger.info(f"Initialized container for lambda '{name}'")
        return container

lambda_registry = LambdaRegistry()

def define_lambda(*, name: str, controllers: list[type], bindings: list | None = None):
    lambda_registry.define(name, controllers, bindings)
