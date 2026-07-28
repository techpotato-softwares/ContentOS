from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.tenants.src.controllers.tenants_controller import TenantsController

define_lambda(name="tenants", controllers=[TenantsController], bindings=[])
handler = create_lambda_handler("tenants")
