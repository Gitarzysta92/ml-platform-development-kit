import json
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import settings


def _s3_client():
    if not settings.s3_bucket:
        return None

    client_config = Config(
        s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"}
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        config=client_config,
    )


def ensure_bucket() -> None:
    client = _s3_client()
    if client is None:
        return
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def write_output_json(job_id: str, payload: Any) -> str | None:
    client = _s3_client()
    if client is None:
        return None

    key = f"{settings.s3_output_prefix.rstrip('/')}/{job_id}.json"
    body = json.dumps(payload).encode("utf-8")
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return f"s3://{settings.s3_bucket}/{key}"

