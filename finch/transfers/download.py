import asyncio
import os
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QProgressBar,
                               QLabel, QPushButton, QScrollArea, QWidget)

from finch.s3 import s3_service
from finch.utils.text import format_size
from finch.utils.ui import center_window
from finch.utils.error import show_error_dialog


@dataclass
class S3DownloadItem:
    bucket_name: str
    key: str
    destination: str
    filename: str
    total_size: Optional[int] = None
    downloaded: int = 0
    status: str = 'pending'
    start_time: float = 0.0
    last_update_time: float = 0.0
    last_downloaded: int = 0
    speed: float = 0.0

    def __post_init__(self):
        self.filename = os.path.basename(self.key)


class DownloadProgressWidget(QWidget):
    def __init__(self, filename: str, display_path: str):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 10)
        self.setLayout(layout)
        self._base_label = display_path
        self.label = QLabel(display_path)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)

    def update_progress(self, percent: int, speed: float = 0):
        speed_str = f" - {format_size(speed)}/s" if speed > 0 else ""
        self.label.setText(f"{self._base_label}... {percent}%{speed_str}")
        self.progress_bar.setValue(percent)

    def mark_done(self, label: str):
        self.label.setText(f"{self._base_label} - {label}")
        self.progress_bar.setEnabled(False)


class MultiDownloadProgressDialog(QDialog):
    _progress_signal = Signal(str, int, float)   # filename, percent, speed
    _completed_signal = Signal(str)              # filename
    _failed_signal = Signal(str, str)            # filename, error

    def __init__(self, file_list: List[tuple], local_file_path: str):
        super().__init__()
        self.setWindowTitle(f"Downloading {len(file_list)} files...")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        center_window(self)

        layout = QVBoxLayout()
        self.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._progress_container = QWidget()
        self._progress_layout = QVBoxLayout()
        self._progress_container.setLayout(self._progress_layout)
        scroll.setWidget(self._progress_container)

        self.status_label = QLabel("Initializing downloads...")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._handle_cancel)

        layout.addWidget(self.status_label)
        layout.addWidget(scroll)
        layout.addWidget(self.cancel_button)

        self._progress_signal.connect(self._update_progress)
        self._completed_signal.connect(self._handle_completion)
        self._failed_signal.connect(self._handle_failure)

        self._total = len(file_list)
        self._done = 0
        self._progress_widgets: Dict[str, DownloadProgressWidget] = {}
        self._gather_task: Optional[asyncio.Task] = None

        # Build download items
        self._items: List[S3DownloadItem] = []
        for bucket_name, key in file_list:
            item = S3DownloadItem(
                bucket_name=bucket_name,
                key=key,
                destination=local_file_path,
                filename=os.path.basename(key),
            )
            try:
                item.total_size = s3_service.get_object_size(bucket_name, key)
            except Exception as e:
                self._failed_signal.emit(item.filename, str(e))
                continue
            self._items.append(item)
            widget = DownloadProgressWidget(item.filename, f"{bucket_name}/{key}")
            self._progress_widgets[item.filename] = widget
            self._progress_layout.addWidget(widget)

        asyncio.ensure_future(self._start_downloads())

    async def _start_downloads(self):
        self._gather_task = asyncio.ensure_future(
            asyncio.gather(*[asyncio.to_thread(self._download_one, item)
                             for item in self._items],
                           return_exceptions=True)
        )
        try:
            await self._gather_task
        except asyncio.CancelledError:
            pass

    def _download_one(self, item: S3DownloadItem):
        item.status = 'downloading'
        item.start_time = time.time()
        item.last_update_time = item.start_time
        os.makedirs(item.destination, exist_ok=True)
        file_path = os.path.join(item.destination, item.filename)
        temp_path = f"{file_path}.part"

        def progress_cb(bytes_amount):
            item.downloaded += bytes_amount
            now = time.time()
            diff = now - item.last_update_time
            if diff >= 0.5:
                item.speed = (item.downloaded - item.last_downloaded) / diff
                item.last_downloaded = item.downloaded
                item.last_update_time = now
            if item.total_size:
                percent = int((item.downloaded / item.total_size) * 100)
                self._progress_signal.emit(item.filename, percent, item.speed)

        try:
            with open(temp_path, 'wb') as f:
                s3_service.download_fileobj(item.bucket_name, item.key, f,
                                            callback=progress_cb)
            os.replace(temp_path, file_path)
            item.status = 'completed'
            self._completed_signal.emit(item.filename)
        except Exception as e:
            item.status = 'failed'
            try:
                os.remove(temp_path)
            except OSError:
                pass
            self._failed_signal.emit(item.filename, str(e))

    def _update_progress(self, filename: str, percent: int, speed: float):
        if filename in self._progress_widgets:
            self._progress_widgets[filename].update_progress(percent, speed)

    def _handle_completion(self, filename: str):
        self._done += 1
        if filename in self._progress_widgets:
            self._progress_widgets[filename].mark_done("Completed")
        if self._done >= self._total:
            self.status_label.setText("All downloads completed!")
            self.cancel_button.setText("Close")
        else:
            self.status_label.setText(
                f"Downloading files... ({self._done}/{self._total} completed)"
            )

    def _handle_failure(self, filename: str, error: str):
        if filename in self._progress_widgets:
            self._progress_widgets[filename].mark_done(
                "Cancelled" if error == "Download cancelled" else f"Failed: {error}"
            )
        if error != "Download cancelled":
            show_error_dialog(f"Failed to download {filename}: {error}")

    def _handle_cancel(self):
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self.status_label.setText("Cancelling downloads...")
        if self._gather_task and not self._gather_task.done():
            self._gather_task.cancel()
        self.accept()

    def closeEvent(self, event):
        if self._gather_task and not self._gather_task.done():
            self._gather_task.cancel()
        event.accept()
