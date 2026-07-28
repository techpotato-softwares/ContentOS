"""JWT secrets in Secrets Manager."""
from __future__ import annotations

import json
import secrets
import string

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class JwtSecretsConstruct(Construct):
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

        print(f"   🔐 Creating JWT secrets for {config.environment}...")

        self.secret = secretsmanager.Secret(
            self,
            "JwtSecret",
            secret_name=config.jwt.secret_id,
            description=f"JWT signing secrets for ArcForge - {config.environment}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {"JWT_REFRESH_SECRET": self._placeholder()}
                ),
                generate_string_key="JWT_SECRET",
                exclude_punctuation=False,
                include_space=False,
                password_length=128,
            ),
            removal_policy=(
                RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY
            ),
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
            "JwtSecretArn",
            value=self.secret.secret_arn,
            description=f"JWT Secrets ARN - {config.environment}",
            export_name=f"ArcForgeJwtSecretArn-{config.environment}",
        )
        print(f"   ✅ Created JWT secret: {config.jwt.secret_id}")

    @staticmethod
    def _placeholder() -> str:
        chars = (
            string.ascii_letters
            + string.digits
            + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        )
        return "".join(secrets.choice(chars) for _ in range(128))

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
