"""S3 buckets from config/s3_config.py."""
from __future__ import annotations

from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct

from config.environment import EnvironmentConfig
from config.s3_config import S3BucketConfig, get_s3_config


class S3Construct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        additional_cors_origins: list[str] | None = None,
    ) -> None:
        super().__init__(scope, construct_id)
        self.buckets: dict[str, s3.Bucket] = {}
        self.bucket_arns: list[str] = []
        self._additional_cors_origins = additional_cors_origins or []

        s3_env = get_s3_config(config.environment)
        print(
            f"   📦 Creating {len(s3_env.buckets)} S3 bucket(s) for {config.environment}..."
        )

        for bucket_cfg in s3_env.buckets:
            bucket = self._create_bucket(bucket_cfg, config)
            self.buckets[bucket_cfg.id] = bucket
            self.bucket_arns.append(bucket.bucket_arn)
            CfnOutput(
                self,
                f"{bucket_cfg.id}BucketName",
                value=bucket.bucket_name,
                description=(
                    f"S3 Bucket Name for {bucket_cfg.id} - {config.environment}"
                ),
                export_name=(
                    f"ArcForge-{bucket_cfg.id}-BucketName-{config.environment}"
                ),
            )
            print(f"   Created S3 bucket: {bucket.bucket_name}")

        self.permissions = self._generate_permissions()

    def _create_bucket(
        self, bucket_cfg: S3BucketConfig, env_config: EnvironmentConfig
    ) -> s3.Bucket:
        bucket_name = f"{bucket_cfg.bucket_name_prefix}-{env_config.environment}"
        cors_origins = [
            o for o in bucket_cfg.cors_allowed_origins if o != "__AUTO__"
        ]
        cors_origins.extend(self._additional_cors_origins)
        if not cors_origins:
            cors_origins = ["*"]

        method_map = {
            "GET": s3.HttpMethods.GET,
            "PUT": s3.HttpMethods.PUT,
            "POST": s3.HttpMethods.POST,
            "DELETE": s3.HttpMethods.DELETE,
            "HEAD": s3.HttpMethods.HEAD,
        }
        cors_rules = None
        if bucket_cfg.enable_cors:
            cors_rules = [
                s3.CorsRule(
                    allowed_headers=["*"],
                    allowed_methods=[
                        method_map[m] for m in bucket_cfg.cors_allowed_methods
                    ],
                    allowed_origins=cors_origins,
                    exposed_headers=["ETag"],
                    max_age=3600,
                )
            ]

        return s3.Bucket(
            self,
            f"{bucket_cfg.id}Bucket",
            bucket_name=bucket_name,
            versioned=bucket_cfg.versioned,
            encryption=(
                s3.BucketEncryption.S3_MANAGED
                if bucket_cfg.encryption
                else s3.BucketEncryption.UNENCRYPTED
            ),
            block_public_access=(
                s3.BlockPublicAccess.BLOCK_ALL
                if bucket_cfg.block_public_access
                else None
            ),
            removal_policy=bucket_cfg.removal_policy,
            auto_delete_objects=bucket_cfg.resolves_auto_delete(),
            cors=cors_rules,
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(7)
                )
            ],
        )

    def _generate_permissions(self) -> list[iam.PolicyStatement]:
        if not self.bucket_arns:
            return []
        return [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:GetObjectVersion",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                resources=[f"{arn}/*" for arn in self.bucket_arns],
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:ListBucket", "s3:GetBucketLocation"],
                resources=list(self.bucket_arns),
            ),
        ]

    def get_bucket(self, bucket_id: str) -> s3.Bucket | None:
        return self.buckets.get(bucket_id)
