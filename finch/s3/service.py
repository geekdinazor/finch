from dataclasses import dataclass
from datetime import datetime
from threading import local
from typing import Callable, List, Optional

import boto3
import keyring
from slugify import slugify

from finch.config import ObjectType
from finch.utils.text import key_display_name


@dataclass
class S3Object:
    key: str
    name: str
    type: ObjectType
    size: int = 0
    last_modified: Optional[datetime] = None
    bucket_name: Optional[str] = None


class S3Service:
    def __init__(self):
        self._credentials: Optional[dict] = None
        self._thread_local = local()
        self._cred_version: int = 0

    @property
    def client(self):
        """Thread-local boto3 client — recreated when credentials change."""
        tl = self._thread_local
        if (not hasattr(tl, 'client') or tl.client is None
                or getattr(tl, 'cred_version', -1) != self._cred_version):
            if self._credentials is None:
                raise RuntimeError("No credentials set. Call set_credential() first.")
            tl.client = boto3.client('s3', **self._credentials)
            tl.cred_version = self._cred_version
        return tl.client

    def set_credential(self, credential: dict) -> None:
        """Switch the active credential — all thread-local clients will be recreated."""
        self._credentials = {
            'endpoint_url': credential.get('endpoint') or None,
            'aws_access_key_id': credential.get('access_key'),
            'aws_secret_access_key': keyring.get_password(
                f'{slugify(credential["name"])}@finch',
                credential.get('access_key'),
            ),
            'region_name': credential.get('region') or None,
        }
        self._cred_version += 1

    # ── Listing ────────────────────────────────────────────────────────────

    def list_buckets(self) -> List[S3Object]:
        response = self.client.list_buckets()
        return [
            S3Object(
                key=b['Name'],
                name=b['Name'],
                type=ObjectType.BUCKET,
                last_modified=b.get('CreationDate'),
            )
            for b in response.get('Buckets', [])
        ]

    def list_objects(self, bucket: str, prefix: str = '') -> List[S3Object]:
        resp = self.client.list_objects(Bucket=bucket, Prefix=prefix, Delimiter='/')
        results: List[S3Object] = []
        for cp in resp.get('CommonPrefixes', []):
            key = cp['Prefix']
            results.append(S3Object(
                key=key,
                name=key_display_name(key),
                type=ObjectType.FOLDER,
                bucket_name=bucket,
            ))
        for obj in resp.get('Contents', []):
            key = obj['Key']
            if key == prefix:
                continue  # skip folder marker itself
            results.append(S3Object(
                key=key,
                name=key_display_name(key),
                type=ObjectType.FILE,
                size=obj['Size'],
                last_modified=obj['LastModified'],
                bucket_name=bucket,
            ))
        return results

    # ── Create ─────────────────────────────────────────────────────────────

    def create_bucket(self, name: str) -> None:
        self.client.create_bucket(Bucket=name)

    def create_folder(self, bucket: str, key: str) -> None:
        if not key.endswith('/'):
            key += '/'
        self.client.put_object(Bucket=bucket, Key=key)

    # ── Delete ─────────────────────────────────────────────────────────────

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def delete_folder(self, bucket: str, prefix: str) -> None:
        paginator = self.client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                self.client.delete_object(Bucket=bucket, Key=obj['Key'])

    def delete_bucket(self, bucket: str) -> None:
        versioning = self.client.get_bucket_versioning(Bucket=bucket)
        if versioning.get('Status') == 'Enabled':
            paginator = self.client.get_paginator('list_object_versions')
            for page in paginator.paginate(Bucket=bucket):
                for v in page.get('Versions', []):
                    self.client.delete_object(Bucket=bucket, Key=v['Key'], VersionId=v['VersionId'])
                for m in page.get('DeleteMarkers', []):
                    self.client.delete_object(Bucket=bucket, Key=m['Key'], VersionId=m['VersionId'])
        else:
            self.delete_folder(bucket, '')
        self.client.delete_bucket(Bucket=bucket)

    def is_bucket_empty(self, bucket: str) -> bool:
        resp = self.client.list_objects_v2(Bucket=bucket, MaxKeys=1)
        return resp.get('KeyCount', 0) == 0

    # ── Presigned URL ──────────────────────────────────────────────────────

    def generate_presigned_url(self, bucket: str, key: str, expiry: int) -> str:
        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiry,
        )

    # ── CORS ───────────────────────────────────────────────────────────────

    def get_bucket_cors(self, bucket: str) -> list:
        resp = self.client.get_bucket_cors(Bucket=bucket)
        return resp.get('CORSRules', [])

    def put_bucket_cors(self, bucket: str, rules: list) -> None:
        if rules:
            self.client.put_bucket_cors(Bucket=bucket, CORSConfiguration={'CORSRules': rules})
        else:
            self.client.delete_bucket_cors(Bucket=bucket)

    # ── ACL ────────────────────────────────────────────────────────────────

    def get_bucket_acl(self, bucket: str) -> dict:
        return self.client.get_bucket_acl(Bucket=bucket)

    def put_bucket_acl(self, bucket: str, acl: dict) -> None:
        self.client.put_bucket_acl(Bucket=bucket, AccessControlPolicy=acl)

    # ── Transfers ──────────────────────────────────────────────────────────

    def upload_fileobj(self, file_obj, bucket: str, key: str,
                       callback: Optional[Callable] = None) -> None:
        self.client.upload_fileobj(file_obj, bucket, key,
                                   Callback=callback if callback else None)

    def get_object_size(self, bucket: str, key: str) -> int:
        return self.client.head_object(Bucket=bucket, Key=key)['ContentLength']

    def download_fileobj(self, bucket: str, key: str, file_obj,
                         callback: Optional[Callable] = None) -> None:
        self.client.download_fileobj(bucket, key, file_obj,
                                     Callback=callback if callback else None)
