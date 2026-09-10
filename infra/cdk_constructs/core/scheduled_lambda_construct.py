"""EventBridge-scheduled Python Lambdas."""
from __future__ import annotations

from dataclasses import dataclass, field

from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from config.environment import EnvironmentConfig
from paths import API_ASSET_EXCLUDES, API_ROOT

_RETENTION: dict[int, logs.RetentionDays] = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
}


@dataclass
class ScheduledLambdaConfig:
    name: str
    handler: str
    description: str
    schedule_expression: str
    memory_size: int | None = None
    timeout: int | None = None
    environment: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class ScheduledLambdaConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        shared_layer: lambda_.LayerVersion,
        scheduled_lambdas: list[ScheduledLambdaConfig],
        db_host: str | None = None,
        s3_bucket_name: str | None = None,
    ) -> None:
        super().__init__(scope, construct_id)
        self.functions: dict[str, lambda_.Function] = {}
        self.rules: dict[str, events.Rule] = {}

        print(f"\n⏰ Creating {len(scheduled_lambdas)} scheduled Lambda function(s)...")

        for cfg in scheduled_lambdas:
            fn, rule = self._create_scheduled_lambda(
                cfg, config, shared_layer, db_host, s3_bucket_name
            )
            self.functions[cfg.name] = fn
            self.rules[cfg.name] = rule

    def _create_scheduled_lambda(
        self,
        lambda_cfg: ScheduledLambdaConfig,
        config: EnvironmentConfig,
        shared_layer: lambda_.LayerVersion,
        db_host: str | None,
        s3_bucket_name: str | None,
    ) -> tuple[lambda_.Function, events.Rule]:
        environment: dict[str, str] = {
            "ENVIRONMENT": config.environment,
            "DB_HOST": db_host or config.database.host,
            "DB_PORT": str(config.database.port),
            "DB_NAME": config.database.name,
            "DB_SSL": str(config.database.ssl).lower(),
            "DB_SECRET_ID": config.db_secret_id,
            "JWT_SECRET_ID": config.jwt.secret_id,
            "STRIPE_SECRET_ID": config.stripe.secret_id,
            "JWT_EXPIRES_IN": config.jwt.expires_in,
            "JWT_REFRESH_EXPIRES_IN": config.jwt.refresh_expires_in,
            "LOG_LEVEL": "INFO" if config.environment == "prod" else "DEBUG",
            **({"S3_BUCKET_NAME": s3_bucket_name} if s3_bucket_name else {}),
            **lambda_cfg.environment,
        }

        fn = lambda_.Function(
            self,
            f"{lambda_cfg.name}Function",
            function_name=f"arcforge-py-{lambda_cfg.name}-{config.environment}",
            description=f"{lambda_cfg.description} - {config.environment}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler=lambda_cfg.handler,
            code=lambda_.Code.from_asset(
                str(API_ROOT), exclude=API_ASSET_EXCLUDES
            ),
            memory_size=lambda_cfg.memory_size or config.lambda_memory_size,
            timeout=Duration.seconds(
                lambda_cfg.timeout or config.lambda_timeout
            ),
            environment=environment,
            layers=[shared_layer],
            tracing=(
                lambda_.Tracing.ACTIVE
                if config.enable_xray
                else lambda_.Tracing.DISABLED
            ),
            log_retention=_RETENTION.get(
                config.log_retention_days, logs.RetentionDays.ONE_WEEK
            ),
        )

        fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:*:*:secret:{config.db_secret_id}*",
                    f"arn:aws:secretsmanager:*:*:secret:{config.jwt.secret_id}*",
                    f"arn:aws:secretsmanager:*:*:secret:{config.stripe.secret_id}*",
                ],
            )
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        rule = events.Rule(
            self,
            f"{lambda_cfg.name}Schedule",
            rule_name=f"arcforge-py-{lambda_cfg.name}-schedule-{config.environment}",
            description=(
                f"Schedule for {lambda_cfg.name}: {lambda_cfg.schedule_expression}"
            ),
            schedule=self._parse_schedule(lambda_cfg.schedule_expression),
            enabled=lambda_cfg.enabled,
        )
        rule.add_target(targets.LambdaFunction(fn))

        cap = lambda_cfg.name[:1].upper() + lambda_cfg.name[1:]
        CfnOutput(
            self,
            f"{lambda_cfg.name}FunctionArn",
            value=fn.function_arn,
            description=f"{lambda_cfg.name} Lambda ARN - {config.environment}",
            export_name=f"ArcForgePy{cap}FunctionArn-{config.environment}",
        )
        CfnOutput(
            self,
            f"{lambda_cfg.name}ScheduleArn",
            value=rule.rule_arn,
            description=f"{lambda_cfg.name} Schedule Rule ARN - {config.environment}",
            export_name=f"ArcForgePy{cap}ScheduleArn-{config.environment}",
        )
        print(
            f"   Created scheduled Lambda: arcforge-py-{lambda_cfg.name}-{config.environment}"
        )
        print(f"   Schedule: {lambda_cfg.schedule_expression}")
        return fn, rule

    @staticmethod
    def _parse_schedule(expression: str) -> events.Schedule:
        if expression.startswith("rate(") or expression.startswith("cron("):
            return events.Schedule.expression(expression)
        return events.Schedule.rate(Duration.hours(6))
