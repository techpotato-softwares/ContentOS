"""Google OAuth secrets in Secrets Manager (0055 auth hygiene — same pattern as JWT).

Secret name: /{APP}/{env}/google-oauth
JSON keys: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

Placeholder values are created at deploy time; replace them in Secrets Manager
(console/CLI). Never commit real client secrets to the repo.
"""
from __future__ import annotations

from aws_cdk import CfnOutput, RemovalPolicy, SecretValue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class GoogleOAuthSecretsConstruct(Construct):
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
        # Mirror JWT: /{APP}/{env}/jwt → /{APP}/{env}/google-oauth
        self.secret_id = config.jwt.secret_id.replace("/jwt", "/google-oauth")

        print(f"   Creating Google OAuth secret placeholder for {config.environment}...")

        self.secret = secretsmanager.Secret(
            self,
            "GoogleOAuthSecret",
            secret_name=self.secret_id,
            description=(
                f"Google OAuth client credentials for ContentOS - {config.environment}. "
                "Replace REPLACE_ME values after deploy; never commit real secrets."
            ),
            secret_object_value={
                "GOOGLE_CLIENT_ID": SecretValue.unsafe_plain_text("REPLACE_ME"),
                "GOOGLE_CLIENT_SECRET": SecretValue.unsafe_plain_text("REPLACE_ME"),
            },
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
            "GoogleOAuthSecretArn",
            value=self.secret.secret_arn,
            description=f"Google OAuth Secrets ARN - {config.environment}",
            export_name=f"ContentOSGoogleOAuthSecretArn-{config.environment}",
        )
        print(f"   Created Google OAuth secret: {self.secret_id}")

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
