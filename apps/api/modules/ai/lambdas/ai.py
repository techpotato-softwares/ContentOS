from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.ai.src.controllers.ai_controller import AiController

define_lambda(name="ai", controllers=[AiController], bindings=[])
handler = create_lambda_handler("ai")
