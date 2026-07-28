"""Optional S3 + CloudFront static site (disabled by default in Python kit)."""
from __future__ import annotations

import os

from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from config.environment import EnvironmentConfig


class StaticSiteConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: EnvironmentConfig,
        ui_build_path: str,
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

        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset(ui_build_path)],
            destination_bucket=self.bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            memory_limit=512,
        )

        self.website_url = f"https://{self.distribution.distribution_domain_name}"

        CfnOutput(
            self,
            "WebsiteURL",
            value=self.website_url,
            description=f"CloudFront URL for ContentOS UI - {config.environment}",
            export_name=f"ContentOS-UI-URL-{config.environment}",
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
