"""Razorpay secrets in Secrets Manager (test or live keys — never commit values)."""
from __future__ import annotations

import json

from aws_cdk import CfnOutput, RemovalPolicy, SecretValue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class RazorpaySecretsConstruct(Construct):
    """Placeholder secret; fill RAZORPAY_* keys in AWS console / CLI after deploy."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
    ) -> None:
        super().__init__(scope, construct_id)
        self.permissions: list[iam.PolicyStatement] = []
        is_prod = config.environment == "prod"

        print(f"   🔐 Creating Razorpay secrets for {config.environment}...")

        placeholder = {
            "RAZORPAY_KEY_ID": "rzp_test_replace_me",
            "RAZORPAY_KEY_SECRET": "replace_me",
            "RAZORPAY_WEBHOOK_SECRET": "whsec_replace_me",
            "RAZORPAY_PLAN_STARTER": "plan_starter_replace_me",
            "RAZORPAY_PLAN_GROWTH": "plan_growth_replace_me",
            "RAZORPAY_PLAN_SCALE": "plan_scale_replace_me",
            "RAZORPAY_PLAN_AGENCY": "plan_agency_replace_me",
        }

        self.secret = secretsmanager.Secret(
            self,
            "RazorpaySecret",
            secret_name=config.razorpay.secret_id,
            description=f"Razorpay billing secrets for ContentOS - {config.environment}",
            secret_string_value=SecretValue.unsafe_plain_text(json.dumps(placeholder)),
            removal_policy=(RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY),
        )
        self.secret_arn = self.secret.secret_arn
        self.permissions.append(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[self.secret.secret_arn],
            )
        )
        CfnOutput(
            self,
            "RazorpaySecretArn",
            value=self.secret.secret_arn,
            description=f"Razorpay Secrets ARN - {config.environment}",
            export_name=f"ContentOSRazorpaySecretArn-{config.environment}",
        )
        print(f"   ✅ Created Razorpay secret: {config.razorpay.secret_id}")

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
