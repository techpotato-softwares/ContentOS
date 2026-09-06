"""S3 + CloudFront: marketing site at `/`, SPA at `/app`."""
from __future__ import annotations

import os
from pathlib import Path

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from config.environment import EnvironmentConfig

# Rewrites /app SPA routes and marketing static-export folders to index.html.
_SPA_APP_FUNCTION = """
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri === '/app' || uri === '/app/') {
    request.uri = '/app/index.html';
    return request;
  }

  if (uri.startsWith('/app/')) {
    var rest = uri.substring(5);
    if (rest.length > 0 && rest.indexOf('.') === -1) {
      request.uri = '/app/index.html';
    }
    return request;
  }

  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (uri.indexOf('.') === -1) {
    request.uri = uri + '/index.html';
  }

  return request;
}
"""


class StaticSiteConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        ui_build_path: str,
        marketing_path: str,
    ) -> None:
        super().__init__(scope, construct_id)
        is_prod = config.environment == "prod"

        print(f"   🌐 Creating static site hosting for {config.environment}...")

        self.bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"contentos-ui-{config.environment}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=is_prod,
            removal_policy=(
                RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY
            ),
            auto_delete_objects=not is_prod,
        )

        oac = cloudfront.S3OriginAccessControl(
            self,
            "OAC",
            origin_access_control_name=f"contentos-ui-oac-{config.environment}",
            description=f"Origin Access Control for ContentOS UI - {config.environment}",
            signing=cloudfront.Signing.SIGV4_ALWAYS,
        )

        use_custom = bool(
            config.custom_domain and config.cloudfront_certificate_arn
        )
        certificate = None
        if use_custom and config.cloudfront_certificate_arn:
            certificate = acm.Certificate.from_certificate_arn(
                self, "CustomCert", config.cloudfront_certificate_arn
            )

        spa_fn = cloudfront.Function(
            self,
            "AppSpaRouter",
            function_name=f"contentos-app-spa-{config.environment}",
            code=cloudfront.FunctionCode.from_inline(_SPA_APP_FUNCTION),
            comment="SPA fallback for /app/* routes",
        )

        dist_kwargs: dict = {
            "comment": f"ContentOS UI - {config.environment}",
            "default_behavior": cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(
                    self.bucket, origin_access_control=oac
                ),
                viewer_protocol_policy=(
                    cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
                ),
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                compress=True,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=spa_fn,
                        event_type=cloudfront.FunctionEventType.VIEWER_REQUEST,
                    )
                ],
            ),
            "default_root_object": "index.html",
            "error_responses": [
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
            "price_class": (
                cloudfront.PriceClass.PRICE_CLASS_ALL
                if is_prod
                else cloudfront.PriceClass.PRICE_CLASS_100
            ),
            "enabled": True,
        }
        if use_custom and config.custom_domain and certificate:
            dist_kwargs["domain_names"] = [config.custom_domain]
            dist_kwargs["certificate"] = certificate
            dist_kwargs["minimum_protocol_version"] = (
                cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021
            )

        self.distribution = cloudfront.Distribution(
            self, "Distribution", **dist_kwargs
        )

        account = os.environ.get("CDK_DEFAULT_ACCOUNT", "*")
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetObject"],
                resources=[self.bucket.arn_for_objects("*")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": (
                            f"arn:aws:cloudfront::{account}:distribution/"
                            f"{self.distribution.distribution_id}"
                        )
                    }
                },
            )
        )

        marketing = Path(marketing_path)
        if not (marketing / "index.html").is_file():
            raise FileNotFoundError(
                f"Marketing build missing at {marketing}. "
                "Run: npm run build:marketing"
            )

        ui = Path(ui_build_path)
        if not (ui / "index.html").is_file():
            raise FileNotFoundError(
                f"Web build missing at {ui}. Run: npm run build:web "
                "(with VITE_BASE=/app/ for deploy)"
            )

        # Marketing website at CloudFront `/`
        s3deploy.BucketDeployment(
            self,
            "DeployMarketing",
            sources=[s3deploy.Source.asset(str(marketing))],
            destination_bucket=self.bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )

        # Application SPA under `/app/`
        s3deploy.BucketDeployment(
            self,
            "DeployApp",
            sources=[s3deploy.Source.asset(str(ui))],
            destination_bucket=self.bucket,
            destination_key_prefix="app",
            distribution=self.distribution,
            distribution_paths=["/app/*"],
            memory_limit=512,
        )

        self.website_url = f"https://{self.distribution.distribution_domain_name}"
        self.app_url = f"{self.website_url}/app/"

        CfnOutput(
            self,
            "WebsiteURL",
            value=self.website_url,
            description=f"Marketing site URL (root) - {config.environment}",
            export_name=f"ContentOS-UI-URL-{config.environment}",
        )
        CfnOutput(
            self,
            "AppURL",
            value=self.app_url,
            description=f"Application URL (/app) - {config.environment}",
            export_name=f"ContentOS-App-URL-{config.environment}",
        )
        CfnOutput(
            self,
            "WebsiteBucketName",
            value=self.bucket.bucket_name,
            description=f"S3 Bucket for ContentOS UI - {config.environment}",
            export_name=f"ContentOS-UI-BucketName-{config.environment}",
        )
        CfnOutput(
            self,
            "DistributionId",
            value=self.distribution.distribution_id,
            description=f"CloudFront Distribution ID - {config.environment}",
            export_name=f"ContentOS-UI-DistributionId-{config.environment}",
        )
