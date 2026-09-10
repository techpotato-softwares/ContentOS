"""Main ContentOS API stack — Python CDK."""
from __future__ import annotations

import os

from aws_cdk import RemovalPolicy, Stack, Tags
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from config.environment import EnvironmentConfig
from config.rds_config import get_rds_config
from cdk_constructs.core.api_gateway_construct import ApiGatewayConstruct
from cdk_constructs.core.lambda_construct import LambdaConstruct
from cdk_constructs.core.scheduled_lambda_construct import (
    ScheduledLambdaConfig,
    ScheduledLambdaConstruct,
)
from cdk_constructs.database.rds_construct import RDSConstruct
from cdk_constructs.database.rds_scheduler_construct import RDSSchedulerConstruct
from cdk_constructs.hosting.static_site_construct import StaticSiteConstruct
from cdk_constructs.permissions.lambda_permissions import (
    IPermissionProvider,
    LambdaPermissions,
)
from cdk_constructs.security.db_secrets_construct import DbSecretsConstruct
from cdk_constructs.security.jwt_secrets_construct import JwtSecretsConstruct
from cdk_constructs.security.stripe_secrets_construct import StripeSecretsConstruct
from cdk_constructs.storage.s3_construct import S3Construct
from paths import LAYER_BUNDLED, MARKETING_PATH, UI_BUILD_PATH
from utils.manifest_reader import read_manifest


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, description=config.description, **kwargs)

        print(f"\n🚀 Building stack: {config.stack_name}")

        for key, value in config.tags.items():
            Tags.of(self).add(key, value)

        manifest = read_manifest()
        permission_providers: list[IPermissionProvider] = []

        rds_construct: RDSConstruct | None = None
        if config.features.rds:
            print("\n🗄️  Creating RDS PostgreSQL instance...")
            rds_construct = RDSConstruct(self, "RDSConstruct", config=config)
            permission_providers.append(rds_construct)

            rds_cfg = get_rds_config(config.environment)
            if rds_cfg.schedule and rds_cfg.schedule.enabled:
                print("\n⏰ Setting up RDS auto-start/stop scheduler...")
                RDSSchedulerConstruct(
                    self,
                    "RDSSchedulerConstruct",
                    config=config,
                    rds_instance=rds_construct.instance,
                    schedule_config=rds_cfg.schedule,
                )

        db_host = (
            rds_construct.instance.instance_endpoint.hostname
            if rds_construct
            else None
        )

        db_secrets: DbSecretsConstruct | None = None
        if not config.features.rds:
            print("\n🔐 Creating DB secret placeholder (Supabase)...")
            db_secrets = DbSecretsConstruct(
                self, "DbSecretsConstruct", config=config
            )
            permission_providers.append(db_secrets)

        print("\n📦 Creating shared Python Lambda layer...")
        shared_layer = lambda_.LayerVersion(
            self,
            "SharedLayer",
            layer_version_name=f"contentos-py-shared-layer-{config.environment}",
            description=(
                "ContentOS Python shared layer — config, DB, router, JWT, training"
            ),
            code=lambda_.Code.from_asset(str(LAYER_BUNDLED)),
            compatible_runtimes=[
                lambda_.Runtime.PYTHON_3_12,
                lambda_.Runtime.PYTHON_3_11,
            ],
            compatible_architectures=[
                lambda_.Architecture.X86_64,
                lambda_.Architecture.ARM_64,
            ],
            removal_policy=(
                RemovalPolicy.RETAIN
                if config.environment == "prod"
                else RemovalPolicy.DESTROY
            ),
        )

        print("\n⚡ Creating Lambda functions...")
        lambda_construct = LambdaConstruct(
            self,
            "LambdaConstruct",
            config=config,
            shared_layer=shared_layer,
            manifest=manifest,
            db_host=db_host,
        )

        static_site: StaticSiteConstruct | None = None
        cloudfront_url: str | None = None
        if config.features.static_site:
            print("\n🌐 Creating static site hosting (S3 + CloudFront)...")
            static_site = StaticSiteConstruct(
                self,
                "StaticSiteConstruct",
                config=config,
                ui_build_path=str(UI_BUILD_PATH),
                marketing_path=str(MARKETING_PATH),
            )
            cloudfront_url = (
                f"https://{static_site.distribution.distribution_domain_name}"
            )

        s3_bucket_name: str | None = None
        if config.features.s3:
            print("\n📦 Creating S3 buckets...")
            additional_cors: list[str] = []
            if cloudfront_url:
                additional_cors.append(cloudfront_url)
            if config.custom_domain:
                additional_cors.append(f"https://{config.custom_domain}")

            s3_construct = S3Construct(
                self,
                "S3Construct",
                config=config,
                additional_cors_origins=additional_cors,
            )
            permission_providers.append(s3_construct)
            files_bucket = s3_construct.get_bucket("files")
            if files_bucket:
                s3_bucket_name = files_bucket.bucket_name

        scheduled: ScheduledLambdaConstruct | None = None
        scheduled_lambdas: list[ScheduledLambdaConfig] = [
            ScheduledLambdaConfig(
                name="weekly-snapshot",
                handler="src.lambdas.weekly_snapshot.handler",
                description="Weekly team performance snapshot emails via Amazon SES",
                schedule_expression="cron(0 9 ? * MON *)",
                timeout=120,
                environment={
                    "SES_ENABLED": "true",
                    "SES_FROM_EMAIL": os.environ.get(
                        "SES_FROM_EMAIL", "noreply@contentos.app"
                    ),
                },
                enabled=True,
            ),
            ScheduledLambdaConfig(
                name="scheduled-publisher",
                handler="src.lambdas.scheduled_publisher.handler",
                description="Publish approved LinkedIn posts when scheduled_at is due",
                schedule_expression="rate(15 minutes)",
                timeout=120,
                enabled=True,
            ),
        ]
        if scheduled_lambdas:
            print("\n⏰ Creating scheduled Lambda functions...")
            scheduled = ScheduledLambdaConstruct(
                self,
                "ScheduledLambdaConstruct",
                config=config,
                shared_layer=shared_layer,
                scheduled_lambdas=scheduled_lambdas,
                db_host=db_host,
                s3_bucket_name=s3_bucket_name,
            )
            # Grant SES send if feature flag or always for weekly snapshot
            for fn in scheduled.functions.values():
                from aws_cdk import aws_iam as iam

                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["ses:SendEmail", "ses:SendRawEmail"],
                        resources=["*"],
                    )
                )

        print("\n🔐 Creating JWT secrets...")
        jwt_secrets = JwtSecretsConstruct(
            self, "JwtSecretsConstruct", config=config
        )
        permission_providers.append(jwt_secrets)

        print("\n🔐 Creating Stripe secrets...")
        stripe_secrets = StripeSecretsConstruct(
            self, "StripeSecretsConstruct", config=config
        )
        permission_providers.append(stripe_secrets)

        if permission_providers:
            print("\n🔐 Applying permissions to Lambda functions...")
            all_fns = {**lambda_construct.functions}
            if scheduled:
                all_fns.update(scheduled.functions)

            LambdaPermissions(
                self,
                "LambdaPermissions",
                config=config,
                lambda_functions=all_fns,
                permission_providers=permission_providers,
            )

            if s3_bucket_name:
                print(
                    f"\n📦 Adding S3_BUCKET_NAME ({s3_bucket_name}) to Lambda environment..."
                )
                for fn in lambda_construct.functions.values():
                    fn.add_environment("S3_BUCKET_NAME", s3_bucket_name)

        print("\n🌐 Creating API Gateway routes...")
        ApiGatewayConstruct(
            self,
            "ApiGatewayConstruct",
            config=config,
            lambda_functions=lambda_construct.functions,
            manifest=manifest,
        )

        print(f"\n✅ Stack {config.stack_name} ready\n")
