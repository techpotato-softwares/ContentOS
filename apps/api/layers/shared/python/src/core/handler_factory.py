from __future__ import annotations
from typing import Any, Callable
from core.service_registry import lambda_registry
from core.router import create_router
from middleware.error_handler import create_error_response
from utils.logger import logger

_states: dict[str, dict[str, Any]] = {}

def create_lambda_handler(lambda_name: str) -> Callable:
    def handler(event, context=None):
        try:
            state = _states.setdefault(lambda_name, {"router": None})
            if state["router"] is None:
                container = lambda_registry.get_container(lambda_name)
                state["router"] = create_router(container, lambda_name)
                logger.info(f"Cold start complete for {lambda_name}")
            return state["router"].handle_request(event, context)
        except Exception as e:
            logger.error("Unhandled handler error", {"error": str(e)})
            return create_error_response(e)
    return handler
