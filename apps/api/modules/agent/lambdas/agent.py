from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.agent.src.controllers.agent_controller import AgentController

define_lambda(name="agent", controllers=[AgentController], bindings=[])
handler = create_lambda_handler("agent")
