"""S3 storage backend.

Uses the boto3 default credential chain (instance role in production,
~/.aws/credentials in development).  No access keys are ever embedded in code.

Server-side encryption: AES256 (SSE-S3), enabled on every put call.
Presigned GET URLs expire in 300 seconds by default.
"""
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import StorageBase

log = logging.getLogger(__name__)

_SSE = "AES256"


class S3Storage(StorageBase):
    def __init__(self, bucket: str, region: str | None = None) -> None:
        self._bucket = bucket
        # Let boto3 resolve credentials from the environment / instance role.
        self._s3 = boto3.client("s3", region_name=region)

    # ------------------------------------------------------------------ text
    def put_text(self, key: str, text: str) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
            ServerSideEncryption=_SSE,
        )

    def get_text(self, key: str) -> str:
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read().decode("utf-8")
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"S3 key not found: {key}") from exc
            raise

    # ----------------------------------------------------------------- bytes
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption=_SSE,
        )

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"S3 key not found: {key}") from exc
            raise

    # --------------------------------------------------------------- helpers
    def delete(self, key: str) -> None:
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            log.warning("S3 delete failed for key '%s': %s", key, exc)

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def presigned_url_or_none(self, key: str, expires_in: int = 300) -> str:
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def health_check(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
            return True
        except (BotoCoreError, ClientError):
            return False
