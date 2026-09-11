"""Platform AI credentials in Secrets Manager (OpenAI / Gemini).

Creates `/{APP}/{env}/ai` with empty key placeholders. Operators paste real
keys in the AWS console after the first deploy — GenerateSecretString only
applies on create, so later CDK deploys will not wipe console updates.
"""
from __future__ import annotations

import json

from aws_cdk import CfnOutput, RemovalPolicy  # pyrefly: ignore[missing-import]
from aws_cdk import aws_iam as iam  # pyrefly: ignore[missing-import]
from aws_cdk import aws_secretsmanager as secretsmanager  # pyrefly: ignore[missing-import]
from constructs import Construct  # pyrefly: ignore[missing-import]

from config.environment import EnvironmentConfig


class AiSecretsConstruct(Construct):
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

        print(f"   🔐 Creating AI secrets for {config.environment}...")

        # Template keys stay empty; generate_string_key is a discardable field
        # required by GenerateSecretString (values filled manually post-deploy).
        self.secret = secretsmanager.Secret(
            self,
            "AiSecret",
            secret_name=config.ai_secret_id,
            description=(
                f"ContentOS platform AI credentials ({config.environment}) — "
                "set OPENAI_API_KEY / GEMINI_API_KEY in console after first deploy"
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {
                        "OPENAI_API_KEY": "",
                        "GEMINI_API_KEY": "",
                        "AI_PROVIDER": "openai",
                    }
                ),
                generate_string_key="_init",
                exclude_punctuation=True,
                password_length=32,
            ),
            removal_policy=(
                RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY
            ),
        )
        self.secret_arn = self.secret.secret_arn
        self.secret_name = config.ai_secret_id
        self.permissions.append(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[self.secret.secret_arn],
            )
        )
        CfnOutput(
            self,
            "AiSecretArn",
            value=self.secret.secret_arn,
            description=f"AI Secrets ARN - {config.environment}",
            export_name=f"ContentOSAiSecretArn-{config.environment}",
        )
        CfnOutput(
            self,
            "AiSecretId",
            value=config.ai_secret_id,
            description=(
                f"AI Secrets Manager id (name) - {config.environment}. "
                "Injected as AI_SECRET_ID; never contains key material."
            ),
            export_name=f"ContentOSAiSecretId-{config.environment}",
        )
        print(
            f"   ✅ Created AI secret: {config.ai_secret_id} "
            "(populate OPENAI_API_KEY / GEMINI_API_KEY in console)"
        )

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
