from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QLabel, QComboBox, QLineEdit,
)

from finch.config import app_settings


_DT_PRESETS = [
    ("%d %b %Y %H:%M",    "01 Jan 2024 14:30"),
    ("%Y-%m-%d %H:%M",    "2024-01-01 14:30"),
    ("%Y-%m-%dT%H:%M:%S", "ISO 8601  -  2024-01-01T14:30:00"),
    ("%m/%d/%Y %H:%M",    "01/01/2024 14:30  (US)"),
    ("%d/%m/%Y %H:%M",    "01/01/2024 14:30  (EU)"),
    (None,                "Custom..."),
]


class UISettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        self._section(layout, "S3 Browser")

        self.check_folder_contents = QCheckBox("Show expand arrow only for non-empty folders")
        self.check_folder_contents.setChecked(app_settings.check_folder_contents)
        layout.addWidget(self.check_folder_contents)

        hint = QLabel("Makes an extra request per folder and may slow down browsing.")
        hint.setObjectName("hint")
        hint.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(hint)

        self.native_file_icons = QCheckBox("Use native file type icons")
        self.native_file_icons.setChecked(app_settings.native_file_icons)
        layout.addWidget(self.native_file_icons)

        hint2 = QLabel("Creates a temporary file per unique extension to resolve the OS icon. "
                        "May cause performance issues with a large number of distinct file types.")
        hint2.setObjectName("hint")
        hint2.setContentsMargins(20, 0, 0, 0)
        hint2.setWordWrap(True)
        layout.addWidget(hint2)

        self._section(layout, "Date / Time")

        current = app_settings.datetime_format
        preset_idx = next((i for i, (f, _) in enumerate(_DT_PRESETS) if f == current), -1)

        self.dt_combo = QComboBox()
        for fmt, label in _DT_PRESETS:
            self.dt_combo.addItem(label, fmt)
        self.dt_combo.setCurrentIndex(preset_idx if preset_idx >= 0 else len(_DT_PRESETS) - 1)
        self.dt_combo.currentIndexChanged.connect(self._on_dt_changed)

        dt_row = QHBoxLayout()
        dt_row.addWidget(QLabel("Format:"))
        dt_row.addWidget(self.dt_combo)
        layout.addLayout(dt_row)

        self.custom_dt = QLineEdit(current)
        self.custom_dt.setPlaceholderText("e.g. %Y-%m-%d %H:%M")
        self.custom_dt.setVisible(preset_idx < 0)
        layout.addWidget(self.custom_dt)

    @staticmethod
    def _section(layout: QVBoxLayout, title: str):
        lbl = QLabel(title)
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        layout.addSpacing(6)
        layout.addWidget(lbl)

    def _on_dt_changed(self, index: int):
        self.custom_dt.setVisible(self.dt_combo.currentData() is None)

    def save(self):
        app_settings.check_folder_contents = self.check_folder_contents.isChecked()
        app_settings.native_file_icons = self.native_file_icons.isChecked()
        fmt = self.dt_combo.currentData()
        app_settings.datetime_format = (self.custom_dt.text() or app_settings.datetime_format) if fmt is None else fmt
        app_settings.save()