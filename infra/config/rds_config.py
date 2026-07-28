"""RDS configuration per environment."""
from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import aws_ec2 as ec2

from config.environment import Environment


@dataclass
class RDSScheduleConfig:
    enabled: bool
    start_schedule: str | None = None
    stop_schedule: str | None = None
    timezone: str | None = "UTC"


@dataclass
class RDSEnvironmentConfig:
    instance_class: ec2.InstanceClass
    instance_size: ec2.InstanceSize
    database_name: str
    username: str
    port: int
    allocated_storage: int
    max_allocated_storage: int
    multi_az: bool
    deletion_protection: bool
    backup_retention_days: int
    publicly_accessible: bool
    schedule: RDSScheduleConfig | None = None


RDS_CONFIG: dict[Environment, RDSEnvironmentConfig] = {
    "dev": RDSEnvironmentConfig(
        database_name="contentos",
        username="contentos_admin",
        port=5432,
        instance_class=ec2.InstanceClass.T4G,
        instance_size=ec2.InstanceSize.MICRO,
        allocated_storage=20,
        max_allocated_storage=50,
        multi_az=False,
        deletion_protection=False,
        backup_retention_days=1,
        publicly_accessible=True,
    ),
    "qa": RDSEnvironmentConfig(
        database_name="contentos",
        username="contentos_admin",
        port=5432,
        instance_class=ec2.InstanceClass.T4G,
        instance_size=ec2.InstanceSize.SMALL,
        allocated_storage=20,
        max_allocated_storage=100,
        multi_az=False,
        deletion_protection=False,
        backup_retention_days=7,
        publicly_accessible=True,
    ),
    "prod": RDSEnvironmentConfig(
        database_name="contentos",
        username="contentos_admin",
        port=5432,
        instance_class=ec2.InstanceClass.T4G,
        instance_size=ec2.InstanceSize.MICRO,
        allocated_storage=20,
        max_allocated_storage=100,
        multi_az=False,
        deletion_protection=True,
        backup_retention_days=1,
        publicly_accessible=True,
        schedule=RDSScheduleConfig(
            enabled=True,
            start_schedule="cron(30 1 ? * MON-SAT *)",
            stop_schedule="cron(30 16 ? * MON-SAT *)",
            timezone="Asia/Kolkata",
        ),
    ),
}


def get_rds_config(env: Environment) -> RDSEnvironmentConfig:
    return RDS_CONFIG[env]
