from __future__ import annotations
import os
import uuid
from dataclasses import dataclass
from config import get_app_config
from utils.logger import logger

@dataclass
class S3Config:
    bucket_name: str
    region: str
    upload_url_expires_in: int = 900
    download_url_expires_in: int = 900

def get_s3_config() -> S3Config:
    cfg = get_app_config()
    return S3Config(
        bucket_name=os.environ.get("S3_BUCKET_NAME", f"contentos-files-{cfg.environment}"),
        region=cfg.region,
    )

def generate_presigned_upload_url(key: str, content_type: str = "application/octet-stream") -> dict:
    import boto3
    conf = get_s3_config()
    client = boto3.client("s3", region_name=conf.region)
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": conf.bucket_name, "Key": key, "ContentType": content_type},
        ExpiresIn=conf.upload_url_expires_in,
    )
    return {"uploadUrl": url, "s3Key": key, "s3Bucket": conf.bucket_name, "expiresIn": conf.upload_url_expires_in}

def generate_presigned_download_url(key: str) -> dict:
    import boto3
    conf = get_s3_config()
    client = boto3.client("s3", region_name=conf.region)
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": conf.bucket_name, "Key": key},
        ExpiresIn=conf.download_url_expires_in,
    )
    return {"downloadUrl": url, "expiresIn": conf.download_url_expires_in}

def generate_s3_key(prefix: str, filename: str) -> str:
    return f"{prefix}/{uuid.uuid4().hex}_{filename}"
