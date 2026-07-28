from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.platform.src.controllers.auth_controller import AuthController

define_lambda(name="auth", controllers=[AuthController], bindings=[])
handler = create_lambda_handler("auth")
