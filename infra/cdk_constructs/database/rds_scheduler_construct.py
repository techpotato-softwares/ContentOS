"""EventBridge + Lambda to start/stop RDS."""
from __future__ import annotations

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_rds as rds
from constructs import Construct

from config.environment import EnvironmentConfig
from config.rds_config import RDSScheduleConfig
from paths import API_ROOT


class RDSSchedulerConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        rds_instance: rds.DatabaseInstance,
        schedule_config: RDSScheduleConfig,
    ) -> None:
        super().__init__(scope, construct_id)
        self.start_rule: events.Rule | None = None
        self.stop_rule: events.Rule | None = None

        if not schedule_config.enabled:
            print(f"   ⏰ RDS scheduling is disabled for {config.environment}")
            self.scheduler_function = lambda_.Function(
                self,
                "DummyScheduler",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.Code.from_inline(
                    'def handler(event, context):\n'
                    '    return {"statusCode": 200, "body": "disabled"}\n'
                ),
                function_name=(
                    f"arcforge-py-rds-scheduler-disabled-{config.environment}"
                ),
            )
            return

        print(f"   ⏰ Setting up RDS scheduling for {config.environment}...")

        self.scheduler_function = lambda_.Function(
            self,
            "SchedulerFunction",
            function_name=f"arcforge-py-rds-scheduler-{config.environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="src.lambdas.rds_scheduler.handler",
            code=lambda_.Code.from_asset(
                str(API_ROOT),
                exclude=[
                    ".venv",
                    ".venv/**",
                    "layers",
                    "layers/**",
                    "tests",
                    "tests/**",
                    "modules",
                    "modules/**",
                    "scripts",
                    "scripts/**",
                    "alembic",
                    "alembic/**",
                    "**/__pycache__",
                    "**/*.pyc",
                    "*.md",
                    ".git",
                    ".git/**",
                    ".env*",
                ],
            ),
            environment={
                "DB_INSTANCE_IDENTIFIER": rds_instance.instance_identifier,
            },
            timeout=Duration.seconds(30),
            memory_size=128,
            description=(
                f"Start/Stop RDS instance for ArcForge Python - {config.environment}"
            ),
        )

        self.scheduler_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds:StartDBInstance",
                    "rds:StopDBInstance",
                    "rds:DescribeDBInstances",
                ],
                resources=[
                    f"arn:aws:rds:{Stack.of(self).region}:*:db:"
                    f"{rds_instance.instance_identifier}"
                ],
            )
        )

        if schedule_config.start_schedule:
            self.start_rule = events.Rule(
                self,
                "StartRule",
                rule_name=f"arcforge-py-rds-start-{config.environment}",
                description=(
                    f"Start RDS instance for ArcForge Python - {config.environment}"
                ),
                schedule=events.Schedule.expression(schedule_config.start_schedule),
                enabled=True,
            )
            self.start_rule.add_target(
                targets.LambdaFunction(
                    self.scheduler_function,
                    event=events.RuleTargetInput.from_object(
                        {
                            "action": "start",
                            "dbInstanceIdentifier": rds_instance.instance_identifier,
                        }
                    ),
                )
            )
            print(f"   🌅 Start schedule: {schedule_config.start_schedule}")

        if schedule_config.stop_schedule:
            self.stop_rule = events.Rule(
                self,
                "StopRule",
                rule_name=f"arcforge-py-rds-stop-{config.environment}",
                description=(
                    f"Stop RDS instance for ArcForge Python - {config.environment}"
                ),
                schedule=events.Schedule.expression(schedule_config.stop_schedule),
                enabled=True,
            )
            self.stop_rule.add_target(
                targets.LambdaFunction(
                    self.scheduler_function,
                    event=events.RuleTargetInput.from_object(
                        {
                            "action": "stop",
                            "dbInstanceIdentifier": rds_instance.instance_identifier,
                        }
                    ),
                )
            )
            print(f"   🌙 Stop schedule: {schedule_config.stop_schedule}")

        CfnOutput(
            self,
            "SchedulerFunctionArn",
            value=self.scheduler_function.function_arn,
            description=f"RDS Scheduler Lambda ARN - {config.environment}",
            export_name=f"ArcForgePy-RDS-SchedulerArn-{config.environment}",
        )
        print(
            f"   ✅ RDS scheduling configured "
            f"(timezone reference: {schedule_config.timezone or 'UTC'})"
        )
