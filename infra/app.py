#!/usr/bin/env python3
"""
ContentOS Python CDK app entrypoint.

Usage (from infra/):
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  cdk synth ApiStack-dev
  cdk deploy ApiStack-qa
"""
from __future__ import annotations

import os
import sys

from aws_cdk import App, Environment

from config.environment import Environment as EnvName
from config.environment import get_environment_config
from stacks.api_stack import ApiStack

app = App()

cdk_env = Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT")
    or os.environ.get("AWS_ACCOUNT_ID"),
    region=os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or "ap-south-1",
)

all_environments: list[EnvName] = ["dev", "qa", "prod"]

target_stack = next(
    (
        arg
        for arg in sys.argv
        if any(f"ApiStack-{e}" in arg for e in all_environments)
    ),
    None,
)

if target_stack:
    target_env = next(
        (e for e in all_environments if f"-{e}" in target_stack), None
    )
    environments_to_synthesize: list[EnvName] = (
        [target_env] if target_env else all_environments
    )
else:
    environments_to_synthesize = all_environments

for environment in environments_to_synthesize:
    config = get_environment_config(environment)
    ApiStack(
        app,
        config.stack_name,
        config=config,
        env=cdk_env,
    )

app.synth()
