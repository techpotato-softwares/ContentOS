"""RDS PostgreSQL construct."""
from __future__ import annotations

import json

from aws_cdk import CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.environment import EnvironmentConfig
from config.rds_config import RDSEnvironmentConfig, get_rds_config


class RDSConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        vpc: ec2.IVpc | None = None,
    ) -> None:
        super().__init__(scope, construct_id)
        rds_config = get_rds_config(config.environment)
        is_prod = config.environment == "prod"

        print(f"   🗄️  Creating RDS PostgreSQL instance for {config.environment}...")

        self.vpc = vpc or self._create_vpc(config, rds_config)
        self.security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"arcforge-db-sg-{config.environment}",
            description=f"Security group for ArcForge RDS - {config.environment}",
            allow_all_outbound=False,
        )

        if rds_config.publicly_accessible:
            self.security_group.add_ingress_rule(
                ec2.Peer.any_ipv4(),
                ec2.Port.tcp(rds_config.port),
                "Allow PostgreSQL access",
            )
        else:
            self.security_group.add_ingress_rule(
                ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
                ec2.Port.tcp(rds_config.port),
                "Allow PostgreSQL access from VPC",
            )

        self.secret = secretsmanager.Secret(
            self,
            "DatabaseSecret",
            secret_name=config.db_secret_id,
            description=f"Database credentials for ArcForge - {config.environment}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps(
                    {"username": rds_config.username}
                ),
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        if is_prod:
            removal_policy = RemovalPolicy.SNAPSHOT
        elif rds_config.deletion_protection:
            removal_policy = RemovalPolicy.RETAIN
        else:
            removal_policy = RemovalPolicy.DESTROY

        self.instance = rds.DatabaseInstance(
            self,
            "Database",
            instance_identifier=f"arcforge-db-{config.environment}",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_18_1
            ),
            instance_type=ec2.InstanceType.of(
                rds_config.instance_class, rds_config.instance_size
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=(
                    ec2.SubnetType.PUBLIC
                    if rds_config.publicly_accessible
                    else ec2.SubnetType.PRIVATE_ISOLATED
                )
            ),
            security_groups=[self.security_group],
            credentials=rds.Credentials.from_secret(self.secret),
            database_name=rds_config.database_name,
            port=rds_config.port,
            allocated_storage=rds_config.allocated_storage,
            max_allocated_storage=rds_config.max_allocated_storage,
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            backup_retention=Duration.days(rds_config.backup_retention_days),
            preferred_backup_window="03:00-04:00",
            preferred_maintenance_window="Sun:04:00-Sun:05:00",
            multi_az=rds_config.multi_az,
            deletion_protection=rds_config.deletion_protection,
            removal_policy=removal_policy,
            enable_performance_insights=is_prod,
            performance_insight_retention=(
                rds.PerformanceInsightRetention.DEFAULT if is_prod else None
            ),
            monitoring_interval=Duration.seconds(60) if is_prod else None,
            publicly_accessible=rds_config.publicly_accessible,
            auto_minor_version_upgrade=True,
        )

        self.permissions = [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[self.secret.secret_arn],
            ),
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["rds-db:connect"],
                resources=[
                    f"arn:aws:rds-db:*:*:dbuser:{self.instance.instance_identifier}/*"
                ],
            ),
        ]

        CfnOutput(
            self,
            "DatabaseEndpoint",
            value=self.instance.instance_endpoint.hostname,
            description=f"RDS Endpoint for ArcForge - {config.environment}",
            export_name=f"ArcForge-RDS-Endpoint-{config.environment}",
        )
        CfnOutput(
            self,
            "DatabasePort",
            value=str(self.instance.instance_endpoint.port),
            description=f"RDS Port for ArcForge - {config.environment}",
            export_name=f"ArcForge-RDS-Port-{config.environment}",
        )
        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.secret.secret_arn,
            description=(
                f"Secrets Manager ARN for database credentials - {config.environment}"
            ),
            export_name=f"ArcForge-RDS-SecretArn-{config.environment}",
        )
        CfnOutput(
            self,
            "DatabaseName",
            value=rds_config.database_name,
            description=f"Database name for ArcForge - {config.environment}",
            export_name=f"ArcForge-RDS-DatabaseName-{config.environment}",
        )
        print(f"   ✅ RDS instance created: arcforge-db-{config.environment}")

    def _create_vpc(
        self, config: EnvironmentConfig, rds_config: RDSEnvironmentConfig
    ) -> ec2.Vpc:
        subnet_configuration = [
            ec2.SubnetConfiguration(
                name="Public",
                subnet_type=ec2.SubnetType.PUBLIC,
                cidr_mask=24,
            )
        ]
        if not rds_config.publicly_accessible:
            subnet_configuration.append(
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            )
        return ec2.Vpc(
            self,
            "DatabaseVpc",
            vpc_name=f"arcforge-vpc-{config.environment}",
            max_azs=2,
            nat_gateways=0 if rds_config.publicly_accessible else 1,
            subnet_configuration=subnet_configuration,
        )
