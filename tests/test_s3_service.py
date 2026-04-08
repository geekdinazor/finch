from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from finch.config import ObjectType
from finch.s3.service import S3Object, S3Service


SAMPLE_CRED = {"name": "test", "access_key": "AKIA1", "endpoint": "", "region": "us-east-1"}


def make_service(mock_keyring=True):
    svc = S3Service()
    if mock_keyring:
        with patch("keyring.get_password", return_value="secret"):
            svc.set_credential(SAMPLE_CRED)
    return svc


class TestS3Object:
    def test_required_fields(self):
        obj = S3Object(key="k", name="n", type=ObjectType.FILE)
        assert obj.key == "k"
        assert obj.name == "n"
        assert obj.type == ObjectType.FILE
        assert obj.size == 0
        assert obj.last_modified is None
        assert obj.bucket_name is None

    def test_optional_fields(self):
        dt = datetime(2024, 1, 1)
        obj = S3Object(key="k", name="n", type=ObjectType.BUCKET, size=100,
                       last_modified=dt, bucket_name="my-bucket")
        assert obj.size == 100
        assert obj.last_modified == dt
        assert obj.bucket_name == "my-bucket"


class TestS3ServiceSetCredential:
    def test_sets_credentials_dict(self):
        svc = S3Service()
        with patch("keyring.get_password", return_value="secret") as mock_kr:
            svc.set_credential(SAMPLE_CRED)
        assert svc._credentials["aws_access_key_id"] == "AKIA1"
        assert svc._credentials["aws_secret_access_key"] == "secret"
        assert svc._credentials["region_name"] == "us-east-1"

    def test_increments_cred_version(self):
        svc = S3Service()
        assert svc._cred_version == 0
        with patch("keyring.get_password", return_value="s"):
            svc.set_credential(SAMPLE_CRED)
        assert svc._cred_version == 1

    def test_empty_endpoint_becomes_none(self):
        svc = S3Service()
        with patch("keyring.get_password", return_value="s"):
            svc.set_credential({**SAMPLE_CRED, "endpoint": ""})
        assert svc._credentials["endpoint_url"] is None

    def test_no_credentials_raises(self):
        svc = S3Service()
        with pytest.raises(RuntimeError, match="No credentials set"):
            _ = svc.client


class TestS3ServiceListBuckets:
    def test_returns_s3_objects(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket-a", "CreationDate": datetime(2024, 1, 1)},
                {"Name": "bucket-b", "CreationDate": datetime(2024, 2, 1)},
            ]
        }
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            buckets = svc.list_buckets()
        assert len(buckets) == 2
        assert buckets[0].name == "bucket-a"
        assert buckets[0].type == ObjectType.BUCKET
        assert buckets[1].key == "bucket-b"

    def test_empty_buckets(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {"Buckets": []}
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            assert svc.list_buckets() == []


class TestS3ServiceListObjects:
    def test_parses_folders_and_files(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_objects.return_value = {
            "CommonPrefixes": [{"Prefix": "folder/"}],
            "Contents": [
                {"Key": "file.txt", "Size": 1024, "LastModified": datetime(2024, 1, 1)},
            ],
        }
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            results = svc.list_objects("my-bucket", "")
        assert len(results) == 2
        folders = [r for r in results if r.type == ObjectType.FOLDER]
        files = [r for r in results if r.type == ObjectType.FILE]
        assert len(folders) == 1
        assert folders[0].name == "folder"
        assert len(files) == 1
        assert files[0].size == 1024

    def test_skips_folder_marker(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_objects.return_value = {
            "CommonPrefixes": [],
            "Contents": [
                {"Key": "prefix/", "Size": 0, "LastModified": datetime(2024, 1, 1)},
                {"Key": "prefix/file.txt", "Size": 512, "LastModified": datetime(2024, 1, 1)},
            ],
        }
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            results = svc.list_objects("my-bucket", "prefix/")
        assert len(results) == 1
        assert results[0].key == "prefix/file.txt"


class TestS3ServiceUpload:
    def test_upload_fileobj_calls_client(self):
        svc = make_service()
        mock_client = MagicMock()
        fake_file = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            svc.upload_fileobj(fake_file, "my-bucket", "folder/file.txt")
        mock_client.upload_fileobj.assert_called_once_with(
            fake_file, "my-bucket", "folder/file.txt", Callback=None
        )

    def test_upload_fileobj_passes_callback(self):
        svc = make_service()
        mock_client = MagicMock()
        cb = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            svc.upload_fileobj(MagicMock(), "b", "k", callback=cb)
        mock_client.upload_fileobj.assert_called_once()
        _, kwargs = mock_client.upload_fileobj.call_args
        assert kwargs["Callback"] is cb


class TestS3ServiceDownload:
    def test_download_fileobj_calls_client(self):
        svc = make_service()
        mock_client = MagicMock()
        fake_file = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            svc.download_fileobj("my-bucket", "folder/file.txt", fake_file)
        mock_client.download_fileobj.assert_called_once_with(
            "my-bucket", "folder/file.txt", fake_file, Callback=None
        )

    def test_download_fileobj_passes_callback(self):
        svc = make_service()
        mock_client = MagicMock()
        cb = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            svc.download_fileobj("b", "k", MagicMock(), callback=cb)
        mock_client.download_fileobj.assert_called_once()
        _, kwargs = mock_client.download_fileobj.call_args
        assert kwargs["Callback"] is cb

    def test_get_object_size(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 4096}
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            size = svc.get_object_size("my-bucket", "file.txt")
        assert size == 4096


class TestS3ServiceIsBucketEmpty:
    def test_empty_bucket(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 0}
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            assert svc.is_bucket_empty("my-bucket") is True

    def test_non_empty_bucket(self):
        svc = make_service()
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 1}
        with patch("boto3.client", return_value=mock_client):
            svc._thread_local = __import__("threading").local()
            assert svc.is_bucket_empty("my-bucket") is False
