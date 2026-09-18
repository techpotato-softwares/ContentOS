from core.handler_factory import create_lambda_handler
from core.service_registry import define_lambda
from modules.tenants.src.controllers.invites_controller import InvitesController
from modules.tenants.src.controllers.tenants_controller import TenantsController

define_lambda(
    name="tenants",
    controllers=[TenantsController, InvitesController],
    bindings=[],
)
handler = create_lambda_handler("tenants")
