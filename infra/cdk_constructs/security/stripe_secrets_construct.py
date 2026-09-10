"""Stripe secrets in Secrets Manager (test or live keys — never commit values)."""
from __future__ import annotations

import json

from aws_cdk import CfnOutput, RemovalPolicy, SecretValue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class StripeSecretsConstruct(Construct):
    """Placeholder secret; fill STRIPE_* keys in AWS console / CLI after deploy."""

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

        print(f"   🔐 Creating Stripe secrets for {config.environment}...")

        placeholder = {
            "STRIPE_SECRET_KEY": "sk_test_replace_me",
            "STRIPE_WEBHOOK_SECRET": "whsec_replace_me",
            "STRIPE_PRICE_STARTER": "price_starter_replace_me",
            "STRIPE_PRICE_GROWTH": "price_growth_replace_me",
            "STRIPE_PRICE_SCALE": "price_scale_replace_me",
            "STRIPE_PRICE_AGENCY": "price_agency_replace_me",
        }

        self.secret = secretsmanager.Secret(
            self,
            "StripeSecret",
            secret_name=config.stripe.secret_id,
            description=f"Stripe billing secrets for ContentOS - {config.environment}",
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
            "StripeSecretArn",
            value=self.secret.secret_arn,
            description=f"Stripe Secrets ARN - {config.environment}",
            export_name=f"ContentOSStripeSecretArn-{config.environment}",
        )
        print(f"   ✅ Created Stripe secret: {config.stripe.secret_id}")

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
