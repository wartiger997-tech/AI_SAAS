"""Object storage abstraction (local filesystem or S3-compatible)."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config

from redliner.config import get_settings

settings = get_settings()


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _local_root() -> Path:
    root = Path(settings.local_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def storage_key(filename: str, tenant_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:160]
    return f"documents/{tenant_id}/{uuid.uuid4().hex}/{safe}"


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    if settings.storage_backend == "s3":
        _s3_client().put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
        )
        return
    path = _local_root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_bytes(key: str) -> bytes:
    if settings.storage_backend == "s3":
        response = _s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
        return bytes(response["Body"].read())
    return (_local_root() / key).read_bytes()


def delete_key(key: str) -> None:
    if settings.storage_backend == "s3":
        _s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)
        return
    path = _local_root() / key
    if path.exists():
        path.unlink()


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def presigned_url(key: str, expires: int = 900) -> str:
    if settings.storage_backend != "s3":
        return f"/files/{key}"
    return str(
        _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
    )


def purge_prefix(prefix: str) -> int:
    """Delete all objects under a prefix. Returns count (best effort)."""
    if settings.storage_backend != "s3":
        root = _local_root() / prefix
        if not root.exists():
            return 0
        count = sum(1 for p in root.rglob("*") if p.is_file())
        shutil.rmtree(root, ignore_errors=True)
        return count
    client = _s3_client()
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix):
        keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if keys:
            client.delete_objects(Bucket=settings.s3_bucket, Delete={"Objects": keys})
            deleted += len(keys)
    return deleted
