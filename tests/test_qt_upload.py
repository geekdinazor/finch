import time
from unittest.mock import MagicMock, patch

import pytest

from finch.transfers.upload import UploadDialog


@pytest.fixture
def upload_dialog(qt_app, tmp_path):
    f = tmp_path / "test.txt"
    f.write_bytes(b"x" * 1024)
    with patch("asyncio.ensure_future"):
        dlg = UploadDialog(str(f), "my-bucket", folder=None, on_success=None)
    yield dlg
    dlg.destroy()


class TestUploadDialogProgress:
    def test_percent_calculation(self, upload_dialog):
        upload_dialog._start_time = time.monotonic() - 1.0
        upload_dialog._uploaded_size = 0
        upload_dialog._on_progress(512, 1024)
        assert upload_dialog._uploaded_size == 512

    def test_progress_reaches_100(self, upload_dialog):
        upload_dialog._start_time = time.monotonic() - 1.0
        upload_dialog._uploaded_size = 0
        received = []
        upload_dialog._progress_signal.connect(received.append)
        upload_dialog._on_progress(1024, 1024)
        assert received == [100]

    def test_start_time_set_on_first_call(self, upload_dialog):
        upload_dialog._start_time = None
        upload_dialog._on_progress(100, 1000)
        assert upload_dialog._start_time is not None

    def test_speed_label_emitted(self, upload_dialog):
        upload_dialog._start_time = time.monotonic() - 1.0
        upload_dialog._uploaded_size = 0
        labels = []
        upload_dialog._label_signal.connect(labels.append)
        upload_dialog._on_progress(512, 1024)
        assert len(labels) == 1
        assert "Uploading" in labels[0]

    def test_folder_strips_trailing_slash(self, tmp_path, qt_app):
        f = tmp_path / "x.txt"
        f.write_bytes(b"x")
        with patch("asyncio.ensure_future"):
            dlg = UploadDialog(str(f), "b", folder="myfolder/")
        assert dlg.folder == "myfolder"
        dlg.destroy()

    def test_upload_succeeded_false_by_default(self, upload_dialog):
        assert upload_dialog.upload_succeeded is False
