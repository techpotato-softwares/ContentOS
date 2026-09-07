"""Environment configuration for ContentOS Python CDK."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Environment = Literal["dev", "qa", "prod"]


@dataclass
class FeatureFlags:
    s3: bool = False
    sqs: bool = False
    dynamodb: bool = False
    ses: bool = False
    vpc: bool = False
    cognito: bool = False
    kms: bool = False
    static_site: bool = False
    rds: bool = False


@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str
    ssl: bool
    username: str = "postgres"


@dataclass
class JwtConfig:
    secret_id: str
    expires_in: str
    refresh_expires_in: str


@dataclass
class EnvironmentConfig:
    environment: Environment
    stack_name: str
    description: str
    db_secret_id: str
    log_retention_days: int
    lambda_memory_size: int
    lambda_timeout: int
    api_stage_name: str
    enable_xray: bool
    tags: dict[str, str]
    features: FeatureFlags
    database: DatabaseConfig
    jwt: JwtConfig
    custom_domain: str | None = None
    cloudfront_certificate_arn: str | None = None


APP = os.environ.get("APP_NAME", "contentos")

_BASE_TAGS = {
    "Project": "ContentOS",
    "Application": "ContentOS",
    "ManagedBy": "CDK",
    "Runtime": "python",
}

# Local + QA: Supabase via **pooler** (IPv4). Direct db.*.supabase.co is IPv6-only
# and fails from Lambda ("Cannot assign requested address").
# Override via DB_HOST / DB_PORT / DB_NAME / DB_USERNAME in CI or shell if needed.
_SUPABASE_PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF") or "oqfodprfkdphkkijypzo"
_SUPABASE_HOST = (
    os.environ.get("DB_HOST")
    or "aws-1-ap-south-1.pooler.supabase.com"
)
_SUPABASE_PORT = int(os.environ.get("DB_PORT") or "5432")  # session mode on pooler
_SUPABASE_DB = os.environ.get("DB_NAME") or "postgres"
# Pooler requires username form: postgres.<project-ref>
_SUPABASE_USER = (
    os.environ.get("DB_USERNAME") or f"postgres.{_SUPABASE_PROJECT_REF}"
)

ENVIRONMENT_CONFIGS: dict[Environment, EnvironmentConfig] = {
    "dev": EnvironmentConfig(
        environment="dev",
        stack_name="ApiStack-dev",
        description="ContentOS API - Development (Supabase)",
        db_secret_id=f"/{APP}/dev/db",
        log_retention_days=7,
        lambda_memory_size=512,
        lambda_timeout=60,
        api_stage_name="dev",
        enable_xray=False,
        tags={**_BASE_TAGS, "Environment": "dev"},
        features=FeatureFlags(s3=True, static_site=True, rds=False),
        database=DatabaseConfig(
            host=_SUPABASE_HOST,
            port=_SUPABASE_PORT,
            name=_SUPABASE_DB,
            ssl=True,
            username=_SUPABASE_USER,
        ),
        jwt=JwtConfig(
            secret_id=f"/{APP}/dev/jwt",
            expires_in="15m",
            refresh_expires_in="1d",
        ),
    ),
    "qa": EnvironmentConfig(
        environment="qa",
        stack_name="api-stack-contentos-qa",
        description="ContentOS API - QA (shared Supabase)",
        db_secret_id=f"/{APP}/qa/db",
        log_retention_days=14,
        lambda_memory_size=512,
        lambda_timeout=60,
        api_stage_name="qa",
        enable_xray=True,
        tags={**_BASE_TAGS, "Environment": "qa"},
        features=FeatureFlags(s3=True, static_site=True, rds=False),
        database=DatabaseConfig(
            host=_SUPABASE_HOST,
            port=_SUPABASE_PORT,
            name=_SUPABASE_DB,
            ssl=True,
            username=_SUPABASE_USER,
        ),
        jwt=JwtConfig(
            secret_id=f"/{APP}/qa/jwt",
            expires_in="15m",
            refresh_expires_in="7d",
        ),
    ),
    "prod": EnvironmentConfig(
        environment="prod",
        stack_name="ApiStack-prod",
        description="ContentOS API - Production (RDS)",
        db_secret_id=f"/{APP}/prod/db",
        log_retention_days=90,
        lambda_memory_size=1024,
        lambda_timeout=60,
        api_stage_name="prod",
        enable_xray=True,
        tags={**_BASE_TAGS, "Environment": "prod"},
        features=FeatureFlags(s3=True, static_site=True, rds=True),
        database=DatabaseConfig(
            host="",
            port=5432,
            name=os.environ.get("DB_NAME") or "contentos",
            ssl=True,
        ),
        jwt=JwtConfig(
            secret_id=f"/{APP}/prod/jwt",
            expires_in="2h",
            refresh_expires_in="30d",
        ),
        custom_domain=os.environ.get("CUSTOM_DOMAIN") or None,
        cloudfront_certificate_arn=os.environ.get("CLOUDFRONT_CERTIFICATE_ARN")
        or None,
    ),
}


def get_environment_config(env: Environment) -> EnvironmentConfig:
    return ENVIRONMENT_CONFIGS[env]
