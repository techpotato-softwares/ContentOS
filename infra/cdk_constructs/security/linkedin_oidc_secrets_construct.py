"""LinkedIn OIDC login secrets in Secrets Manager (same pattern as Google OAuth).

Secret name: /{APP}/{env}/linkedin-oidc
JSON keys: LINKEDIN_OIDC_CLIENT_ID, LINKEDIN_OIDC_CLIENT_SECRET

Separate from publishing LinkedIn env (LINKEDIN_CLIENT_ID / social callback).
Never commit real client secrets.
"""
from __future__ import annotations

from aws_cdk import CfnOutput, RemovalPolicy, SecretValue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class LinkedInOidcSecretsConstruct(Construct):
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
        self.secret_id = config.jwt.secret_id.replace("/jwt", "/linkedin-oidc")

        print(f"   Creating LinkedIn OIDC secret placeholder for {config.environment}...")

        self.secret = secretsmanager.Secret(
            self,
            "LinkedInOidcSecret",
            secret_name=self.secret_id,
            description=(
                f"LinkedIn OIDC login credentials for ContentOS - {config.environment}. "
                "Replace REPLACE_ME after deploy; never commit real secrets. "
                "Not used for LinkedIn publishing SocialAccount connect."
            ),
            secret_object_value={
                "LINKEDIN_OIDC_CLIENT_ID": SecretValue.unsafe_plain_text("REPLACE_ME"),
                "LINKEDIN_OIDC_CLIENT_SECRET": SecretValue.unsafe_plain_text(
                    "REPLACE_ME"
                ),
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
            "LinkedInOidcSecretArn",
            value=self.secret.secret_arn,
            description=f"LinkedIn OIDC Secrets ARN - {config.environment}",
            export_name=f"ContentOSLinkedInOidcSecretArn-{config.environment}",
        )
        print(f"   Created LinkedIn OIDC secret: {self.secret_id}")

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
