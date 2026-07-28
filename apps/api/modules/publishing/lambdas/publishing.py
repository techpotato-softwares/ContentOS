from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.publishing.src.controllers.publishing_controller import PublishingController

define_lambda(name="publishing", controllers=[PublishingController], bindings=[])
handler = create_lambda_handler("publishing")
