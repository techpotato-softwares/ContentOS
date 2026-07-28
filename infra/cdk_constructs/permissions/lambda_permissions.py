"""Aggregate IAM permissions onto Lambda functions."""
from __future__ import annotations

from typing import Protocol

from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from config.environment import EnvironmentConfig


class IPermissionProvider(Protocol):
    permissions: list[iam.PolicyStatement]


class LambdaPermissions(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        lambda_functions: dict[str, lambda_.Function],
        permission_providers: list[IPermissionProvider],
    ) -> None:
        super().__init__(scope, construct_id)
        self.all_permissions: list[iam.PolicyStatement] = []

        for provider in permission_providers:
            self.all_permissions.extend(provider.permissions)

        if config.enable_xray:
            self.all_permissions.append(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                        "xray:GetSamplingStatisticSummaries",
                    ],
                    resources=["*"],
                )
            )

        for fn in lambda_functions.values():
            for permission in self.all_permissions:
                fn.add_to_role_policy(permission)

        print(
            f"   🔐 Applied {len(self.all_permissions)} permission statements to "
            f"{len(lambda_functions)} Lambda function(s)"
        )

    @staticmethod
    def create_secrets_manager_permission(
        secret_ids: list[str],
    ) -> iam.PolicyStatement:
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["secretsmanager:GetSecretValue"],
            resources=[
                f"arn:aws:secretsmanager:*:*:secret:{sid}*" for sid in secret_ids
            ],
        )
