from unittest.mock import patch, MagicMock

# Stub out PySide6 Qt classes so no display is required
import sys
from unittest.mock import MagicMock

for mod in [
    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets",
]:
    sys.modules.setdefault(mod, MagicMock())

from finch.transfers.download import S3DownloadItem


class TestS3DownloadItem:
    def test_filename_with_path(self):
        item = S3DownloadItem(
            bucket_name="my-bucket",
            key="folder/sub/file.txt",
            destination="/tmp",
            filename="",
        )
        assert item.filename == "file.txt"

    def test_filename_root_key(self):
        item = S3DownloadItem(
            bucket_name="my-bucket",
            key="file.txt",
            destination="/tmp",
            filename="",
        )
        assert item.filename == "file.txt"

    def test_filename_preserves_extension(self):
        item = S3DownloadItem(
            bucket_name="b",
            key="data/report.csv",
            destination="/tmp",
            filename="",
        )
        assert item.filename == "report.csv"

    def test_initial_status_pending(self):
        item = S3DownloadItem(bucket_name="b", key="f.txt", destination="/tmp", filename="")
        assert item.status == "pending"

    def test_initial_downloaded_zero(self):
        item = S3DownloadItem(bucket_name="b", key="f.txt", destination="/tmp", filename="")
        assert item.downloaded == 0

    def test_total_size_defaults_none(self):
        item = S3DownloadItem(bucket_name="b", key="f.txt", destination="/tmp", filename="")
        assert item.total_size is None
