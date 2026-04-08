from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QLabel, QComboBox, QLineEdit, QPushButton, QFileDialog,
)
from PySide6.QtCore import Qt

from finch.config import app_settings

_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LoggingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(8)

        self.logging_enabled = QCheckBox("Enable debug logging")
        self.logging_enabled.setChecked(app_settings.logging_enabled)
        layout.addWidget(self.logging_enabled)

        self._sub = QWidget()
        sub_layout = QVBoxLayout(self._sub)
        sub_layout.setContentsMargins(20, 0, 0, 0)
        sub_layout.setSpacing(4)

        self.logging_to_file = QCheckBox("Write logs to file")
        self.logging_to_file.setChecked(app_settings.logging_to_file)
        sub_layout.addWidget(self.logging_to_file)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Log file:"))
        self.log_path = QLineEdit(app_settings.log_file_path)
        path_row.addWidget(self.log_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        sub_layout.addLayout(path_row)

        levels_lbl = QLabel("Logger levels:")
        font = levels_lbl.font()
        font.setBold(True)
        levels_lbl.setFont(font)
        levels_lbl.setContentsMargins(0, 8, 0, 2)
        sub_layout.addWidget(levels_lbl)

        self._level_combos: dict[str, QComboBox] = {}
        for name, default in app_settings.logger_levels.items():
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setObjectName("logger-name")
            lbl.setFixedWidth(180)
            row.addWidget(lbl)
            combo = QComboBox()
            combo.addItems(_LOG_LEVELS)
            combo.setCurrentText(default)
            row.addWidget(combo)
            row.addStretch()
            sub_layout.addLayout(row)
            self._level_combos[name] = combo

        self._sub.setVisible(app_settings.logging_enabled)
        layout.addWidget(self._sub)

        self.logging_enabled.toggled.connect(self._sub.setVisible)

    def _browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select log file", self.log_path.text(),
            "Log files (*.log);;All files (*)",
        )
        if path:
            self.log_path.setText(path)

    def save(self):
        app_settings.logging_enabled = self.logging_enabled.isChecked()
        app_settings.logging_to_file = self.logging_to_file.isChecked()
        app_settings.log_file_path   = self.log_path.text() or app_settings.log_file_path
        for name, combo in self._level_combos.items():
            app_settings.logger_levels[name] = combo.currentText()
        app_settings.save()
        app_settings.apply_logging()