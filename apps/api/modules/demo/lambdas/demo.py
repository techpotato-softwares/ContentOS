from core.service_registry import define_lambda
from core.handler_factory import create_lambda_handler
from modules.demo.src.controllers.demo_controller import DemoItemController

define_lambda(name="demo", controllers=[DemoItemController], bindings=[])
handler = create_lambda_handler("demo")
