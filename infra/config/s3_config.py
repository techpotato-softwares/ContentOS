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
    # When None, derived from removal_policy == DESTROY.
    auto_delete_objects: bool | None = None
    cors_allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    cors_allowed_methods: list[str] = field(
        default_factory=lambda: ["GET", "PUT", "POST", "DELETE", "HEAD"]
    )

    def resolves_auto_delete(self) -> bool:
        if self.auto_delete_objects is not None:
            return self.auto_delete_objects
        return self.removal_policy == RemovalPolicy.DESTROY


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
                auto_delete_objects=True,
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
                # Versioning leaves delete-markers that can block CFN destroy
                # even with empty "current" objects; keep off for ephemeral QA.
                versioned=False,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True,
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
                auto_delete_objects=False,
                cors_allowed_origins=["__AUTO__"],
            )
        ]
    ),
}


def get_s3_config(env: Environment) -> S3EnvironmentConfig:
    return S3_CONFIG[env]
