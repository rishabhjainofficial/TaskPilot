import os
import uuid
from typing import Optional
from app.config import get_settings

settings = get_settings()


class StorageClient:
    def __init__(self):
        self.endpoint = settings.S3_ENDPOINT
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.bucket = settings.S3_BUCKET
        self.region = settings.S3_REGION

    def generate_storage_key(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        filename: str,
    ) -> str:
        safe_filename = filename.replace("/", "_").replace(" ", "_")
        unique_id = uuid.uuid4().hex[:8]
        return f"orgs/{org_id}/projects/{project_id}/tasks/{task_id}/{unique_id}_{safe_filename}"

    def generate_presigned_put_url(
        self,
        storage_key: str,
        content_type: str,
        expires_seconds: int = 900,
    ) -> str:
        # In test or local dev without live S3, return a deterministic presigned-like URL
        if settings.ENVIRONMENT == "test":
            return f"https://mock-s3.local/{self.bucket}/{storage_key}?upload_ticket=mock"

        try:
            import boto3
            from botocore.config import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )
            return s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": storage_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_seconds,
            )
        except Exception:
            return f"{self.endpoint}/{self.bucket}/{storage_key}?ticket={uuid.uuid4().hex}"

    def generate_presigned_get_url(
        self,
        storage_key: str,
        expires_seconds: int = 300,
    ) -> str:
        if settings.ENVIRONMENT == "test":
            return f"https://mock-s3.local/{self.bucket}/{storage_key}?download_ticket=mock"

        try:
            import boto3
            from botocore.config import Config

            s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )
            return s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": storage_key,
                },
                ExpiresIn=expires_seconds,
            )
        except Exception:
            return f"{self.endpoint}/{self.bucket}/{storage_key}"


storage_client = StorageClient()
