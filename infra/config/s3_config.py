"""S3 bucket configuration per environment."""
from __future__ import annotations

from dataclasses import dataclass, field

from aws_cdk import RemovalPolicy

from config.environment import Environment


@dataclass
class S3BucketConfig:
    id: str
    bucket_name_prefix: str
    versioned: bool = False
    enable_cors: bool = True
    block_public_access: bool = True
    encryption: bool = True
    removal_policy: RemovalPolicy = RemovalPolicy.RETAIN
    cors_allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    cors_allowed_methods: list[str] = field(
        default_factory=lambda: ["GET", "PUT", "POST", "DELETE", "HEAD"]
    )


@dataclass
class S3EnvironmentConfig:
    buckets: list[S3BucketConfig]


S3_CONFIG: dict[Environment, S3EnvironmentConfig] = {
    "dev": S3EnvironmentConfig(
        buckets=[
            S3BucketConfig(
                id="files",
                bucket_name_prefix="contentos-files",
                versioned=False,
                removal_policy=RemovalPolicy.DESTROY,
                cors_allowed_origins=[
                    "__AUTO__",
                    "http://localhost:3000",
                    "http://localhost:4000",
                    "http://localhost:4001",
                ],
            )
        ]
    ),
    "qa": S3EnvironmentConfig(
        buckets=[
            S3BucketConfig(
                id="files",
                bucket_name_prefix="contentos-files",
                versioned=True,
                removal_policy=RemovalPolicy.DESTROY,
                cors_allowed_origins=["__AUTO__"],
            )
        ]
    ),
    "prod": S3EnvironmentConfig(
        buckets=[
            S3BucketConfig(
                id="files",
                bucket_name_prefix="contentos-files",
                versioned=True,
                removal_policy=RemovalPolicy.RETAIN,
                cors_allowed_origins=["__AUTO__"],
            )
        ]
    ),
}


def get_s3_config(env: Environment) -> S3EnvironmentConfig:
    return S3_CONFIG[env]
