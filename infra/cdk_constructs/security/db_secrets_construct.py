"""Supabase / external DB secret placeholders in Secrets Manager (dev + QA).

Prod uses RDSConstruct, which creates its own secret. For non-RDS envs this
construct creates `/contentos/{env}/db` with username from EnvironmentConfig and
an auto-generated password. Update the password in Secrets Manager to your
Supabase password after the first deploy — CDK will not overwrite it on later
deploys (GenerateSecretString only applies on create).
"""
from __future__ import annotations

import json

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig


class DbSecretsConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
    ) -> None:
        super().__init__(scope, construct_id)
        self.permissions: list[iam.PolicyStatement] = []

        if config.features.rds:
            raise ValueError(
                "DbSecretsConstruct is only for non-RDS envs; prod uses RDSConstruct"
            )

        print(f"   🔐 Creating DB secret placeholder for {config.environment}...")

        self.secret = secretsmanager.Secret(
            self,
            "DatabaseSecret",
            secret_name=config.db_secret_id,
            description=(
                f"ContentOS DB credentials ({config.environment}) — "
                "set password to your Supabase DB password after first deploy"
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {"username": config.database.username}
                ),
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
            removal_policy=(
                RemovalPolicy.RETAIN
                if config.environment == "prod"
                else RemovalPolicy.DESTROY
            ),
        )
        self.secret_arn = self.secret.secret_arn
        self.permissions.append(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[self.secret.secret_arn],
            )
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.secret.secret_arn,
            description=f"DB Secrets ARN - {config.environment}",
            export_name=f"ContentOSDbSecretArn-{config.environment}",
        )
        print(
            f"   ✅ Created DB secret {config.db_secret_id} "
            "(update password in console to match Supabase)"
        )

    def grant_read(self, grantee: iam.IGrantable) -> iam.Grant:
        return self.secret.grant_read(grantee)
