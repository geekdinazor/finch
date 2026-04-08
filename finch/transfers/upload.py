import asyncio
import logging
import os
import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QProgressDialog

from finch.s3 import s3_service
from finch.utils.text import format_size

log = logging.getLogger(__name__)


class UploadDialog(QProgressDialog):
    _progress_signal = Signal(int)   # percent 0-100
    _label_signal = Signal(str)      # label with speed info
    _completed_signal = Signal()
    _failed_signal = Signal(str)     # error message

    def __init__(self, file_path, bucket_name, folder=None, on_success=None):
        self._file_name = os.path.basename(file_path)
        super().__init__(f"Uploading {self._file_name}...", "Cancel", 0, 100)
        self.file_path = file_path
        self.bucket_name = bucket_name
        self.folder = folder[:-1] if folder else None
        self._on_success = on_success
        self._uploaded_size = 0
        self._start_time = None

        self.upload_succeeded = False

        self._progress_signal.connect(self.setValue)
        self._label_signal.connect(self.setLabelText)
        self._completed_signal.connect(self._on_completed)
        self._failed_signal.connect(self._on_failed)

        asyncio.ensure_future(self._start_upload())

    async def _start_upload(self):
        log.debug("_start_upload: started for %s → bucket=%s folder=%s",
                  self._file_name, self.bucket_name, self.folder)
        try:
            await asyncio.to_thread(self._upload_sync)
            log.debug("_start_upload: _upload_sync finished, emitting completed")
            self._completed_signal.emit()
        except Exception as e:
            log.exception("_start_upload: upload failed")
            self._failed_signal.emit(str(e))

    def _upload_sync(self):
        file_name = os.path.basename(self.file_path)
        total_size = os.path.getsize(self.file_path)
        s3_path = f"{self.folder}/{file_name}" if self.folder else file_name
        with open(self.file_path, 'rb') as f:
            s3_service.upload_fileobj(f, self.bucket_name, s3_path,
                                      callback=lambda n: self._on_progress(n, total_size))

    def _on_progress(self, bytes_amount: int, total_size: int):
        if self._start_time is None:
            self._start_time = time.monotonic()
        self._uploaded_size += bytes_amount
        percent = int((self._uploaded_size / total_size) * 100)
        elapsed = time.monotonic() - self._start_time
        speed = self._uploaded_size / elapsed if elapsed > 0 else 0
        speed_str = f"{format_size(speed)}/s" if speed > 0 else "…"
        self._label_signal.emit(f"Uploading {self._file_name}… {speed_str}")
        self._progress_signal.emit(percent)

    def _on_completed(self):
        log.debug("_on_completed: upload done, invoking on_success callback then accept()")
        self.upload_succeeded = True
        if self._on_success:
            self._on_success()
        self.accept()

    def _on_failed(self, message: str):
        log.debug("_on_failed: %s", message)
        from finch.utils.error import show_error_dialog
        show_error_dialog(message)
        self.reject()
