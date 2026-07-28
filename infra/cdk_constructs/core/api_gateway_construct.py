"""API Gateway routes from app-manifest.json."""
from __future__ import annotations

from aws_cdk import CfnOutput, Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from config.environment import EnvironmentConfig
from utils.manifest_reader import AppManifest, RouteManifestEntry

CORS_RESPONSE_HEADERS = {
    "Access-Control-Allow-Origin": "'*'",
    "Access-Control-Allow-Headers": (
        "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token'"
    ),
    "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
}


class ApiGatewayConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        lambda_functions: dict[str, lambda_.Function],
        manifest: AppManifest,
    ) -> None:
        super().__init__(scope, construct_id)

        self.api = apigateway.RestApi(
            self,
            "ContentOSApi",
            rest_api_name=f"contentos-api-{config.environment}",
            description=config.description,
            deploy_options=apigateway.StageOptions(
                stage_name=config.api_stage_name,
                tracing_enabled=config.enable_xray,
                metrics_enabled=True,
                logging_level=apigateway.MethodLoggingLevel.INFO,
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
                max_age=Duration.days(1),
            ),
        )

        self._add_gateway_responses()
        self._create_routes_from_manifest(manifest, lambda_functions)

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            description=f"API Gateway URL for {config.environment}",
            export_name=f"ContentOSApiUrl-{config.environment}",
        )

    def _add_gateway_responses(self) -> None:
        responses = [
            ("Default4XX", apigateway.ResponseType.DEFAULT_4_XX),
            ("Default5XX", apigateway.ResponseType.DEFAULT_5_XX),
            ("AccessDenied", apigateway.ResponseType.ACCESS_DENIED),
            ("Unauthorized", apigateway.ResponseType.UNAUTHORIZED),
            ("ExpiredToken", apigateway.ResponseType.EXPIRED_TOKEN),
            (
                "MissingAuthToken",
                apigateway.ResponseType.MISSING_AUTHENTICATION_TOKEN,
            ),
            ("InvalidApiKey", apigateway.ResponseType.INVALID_API_KEY),
            ("Throttled", apigateway.ResponseType.THROTTLED),
            ("QuotaExceeded", apigateway.ResponseType.QUOTA_EXCEEDED),
        ]
        for name, response_type in responses:
            self.api.add_gateway_response(
                name,
                type=response_type,
                response_headers=CORS_RESPONSE_HEADERS,
            )
        print("   ✅ Added CORS headers to Gateway Responses")

    def _create_routes_from_manifest(
        self,
        manifest: AppManifest,
        lambda_functions: dict[str, lambda_.Function],
    ) -> None:
        resource_cache: dict[str, apigateway.IResource] = {"": self.api.root}

        for lambda_name, lambda_cfg in manifest.lambdas.items():
            fn = lambda_functions.get(lambda_name)
            if not fn:
                print(
                    f"⚠️  Lambda function '{lambda_name}' not found, skipping routes"
                )
                continue
            integration = apigateway.LambdaIntegration(fn)
            for route in lambda_cfg.routes:
                self._add_route(route, integration, resource_cache)

        print(f"   Created {len(resource_cache) - 1} API resources")

    def _add_route(
        self,
        route: RouteManifestEntry,
        integration: apigateway.LambdaIntegration,
        resource_cache: dict[str, apigateway.IResource],
    ) -> None:
        resource = self._get_or_create_resource(route.path, resource_cache)
        resource.add_method(route.method, integration)
        print(
            f"   {route.method:<7} {route.path} → {route.controller}.{route.action}()"
        )

    def _get_or_create_resource(
        self,
        path: str,
        resource_cache: dict[str, apigateway.IResource],
    ) -> apigateway.IResource:
        normalized = path if path.startswith("/") else f"/{path}"
        if normalized in resource_cache:
            return resource_cache[normalized]

        segments = [s for s in normalized.split("/") if s]
        current = self.api.root
        current_path = ""
        for segment in segments:
            current_path = f"{current_path}/{segment}"
            if current_path in resource_cache:
                current = resource_cache[current_path]
            else:
                current = current.add_resource(segment)
                resource_cache[current_path] = current
        return current
