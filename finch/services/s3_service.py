from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

import boto3
import keyring
from slugify import slugify

class ObjectType(str, Enum):
    """ Enum for S3 object types """
    BUCKET = "Bucket"
    FOLDER = "Folder"
    FILE = "File"

@dataclass
class S3Object:
    name: str
    type: ObjectType
    size: int = 0
    last_modified: Optional[datetime] = None
    bucket: Optional[str] = None
    key: Optional[str] = None

class S3Service:
    def __init__(self):
        self.s3_session = boto3.session.Session()
        self.s3_resource = None

    def set_credential(self, credential):
        if not credential:
            raise Exception("Invalid credential data")
            
        try:
            self.s3_resource = boto3.resource('s3',
                                         endpoint_url=credential.get('endpoint'),
                                         aws_access_key_id=credential.get('access_key'),
                                         aws_secret_access_key=keyring.get_password(
                                             f'{slugify(credential["name"])}@finch',
                                             credential.get('access_key')
                                         ),
                                         region_name=credential.get('region'),
                                         use_ssl = credential.get('use_ssl'),
                                         verify=credential.get('verify_ssl')
                                         )
            # Test the connection
            self.s3_resource.meta.client.list_buckets()
        except Exception as e:
            self.s3_resource = None
            raise Exception(f"Failed to configure S3 service: {str(e)}")

    def list_buckets(self):
        try:
            objects: List[S3Object] = []
            response = self.s3_resource.meta.client.list_buckets()
            for bucket in response.get("Buckets", []):
                objects.append(S3Object(
                    name=bucket.get('Name'),
                    type=ObjectType.BUCKET,
                    size=0,
                    last_modified=bucket.get('CreationDate')
                ))
            return objects
        except Exception as e:
            self.s3_resource = None
            raise Exception(f"Failed to list buckets: {str(e)}")

    def list_objects(self, bucket: str, prefix: str = "", max_keys: int = None) -> List[S3Object]:
        """List objects in a bucket with prefix"""
        try:
            paginator = self.s3_resource.meta.client.get_paginator('list_objects_v2')
            
            # Add MaxKeys if specified
            paginate_config = {'Bucket': bucket, 'Prefix': prefix, 'Delimiter': '/'}
            if max_keys is not None:
                paginate_config['PaginationConfig'] = {'MaxItems': max_keys}
            
            for page in paginator.paginate(**paginate_config):
                # Handle folders (CommonPrefixes)
                for prefix_dict in page.get('CommonPrefixes', []):
                    prefix_path = prefix_dict.get('Prefix', '')
                    if prefix_path:
                        folder_name = prefix_path.rstrip('/').split('/')[-1]
                        yield S3Object(
                            name=folder_name,
                            type=ObjectType.FOLDER,
                            bucket=bucket,
                            key=prefix_path.rstrip('/')
                        )

                # Handle files (Contents)
                for obj in page.get('Contents', []):
                    key = obj.get('Key', '')
                    if key and not key.endswith('/'):  # Skip folder markers
                        file_name = key.split('/')[-1]
                        yield S3Object(
                            name=file_name,
                            type=ObjectType.FILE,
                            bucket=bucket,
                            key=key,
                            size=obj.get('Size', 0),
                            last_modified=obj.get('LastModified')
                        )

        except Exception as e:
            self.s3_resource = None
            raise Exception(f"Failed to list objects: {str(e)}")

    def create_bucket(self, bucket_name: str):
        """Create a new bucket"""
        try:
            self.s3_resource.create_bucket(Bucket=bucket_name)
        except Exception as e:
            raise Exception(f"Failed to create bucket: {str(e)}")

    def create_folder(self, bucket: str, folder_path: str):
        """Create a new folder (empty object ending with '/')"""
        try:
            # Ensure the folder path ends with '/'
            if not folder_path.endswith('/'):
                folder_path += '/'
            
            # Create empty object with folder path
            self.s3_resource.Object(bucket, folder_path).put(Body='')
        except Exception as e:
            raise Exception(f"Failed to create folder: {str(e)}")

    def delete_object(self, bucket: str, key: str):
        """Delete an object and all its contents if it's a folder"""
        try:
            if key.endswith('/'):
                # It's a folder - delete all contents first
                paginator = self.s3_resource.meta.client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=bucket, Prefix=key):
                    objects_to_delete = [{'Key': obj['Key']} for obj in page.get('Contents', [])]
                    if objects_to_delete:
                        self.s3_resource.meta.client.delete_objects(
                            Bucket=bucket,
                            Delete={'Objects': objects_to_delete}
                        )
                # Delete the folder marker itself
                self.s3_resource.Object(bucket, key).delete()
            else:
                # Single file deletion
                self.s3_resource.Object(bucket, key).delete()
        except Exception as e:
            raise Exception(f"Failed to delete object: {str(e)}")



