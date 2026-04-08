from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QLabel, QDialogButtonBox,
)

from finch.settings.credentials import CredentialsPage
from finch.settings.log_settings import LoggingPage
from finch.settings.ui_settings import UISettingsPage
from finch.utils.error import show_error_dialog
from finch.utils.ui import center_window, resource_path


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(resource_path("img/icon.png")).pixmap(QSize(80, 80)))
        icon_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel("Finch S3 Client")
        title_label.setFont(QFont("sans", 24))
        title_label.setAlignment(Qt.AlignCenter)

        italic = QFont("sans", 11)
        italic.setItalic(True)

        subtitle_label = QLabel(
            'In memoriam of '
            '<a href="https://personofinterest.fandom.com/wiki/Root">Root</a>'
            ' and '
            '<a href="https://personofinterest.fandom.com/wiki/Harold_Finch">Harold Finch</a>'
        )
        subtitle_label.setFont(italic)
        subtitle_label.setOpenExternalLinks(True)
        subtitle_label.setAlignment(Qt.AlignCenter)

        version_label = QLabel("v1.0 BETA")
        version_label.setFont(italic)
        version_label.setAlignment(Qt.AlignCenter)

        contributors_label = QLabel("<strong>Contributors:</strong>")
        contributors_label.setContentsMargins(0, 16, 0, 0)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(version_label)
        layout.addWidget(contributors_label)
        for name in ["Furkan Kalkan <furkankalkan@mantis.com.tr>"]:
            layout.addWidget(QLabel(name))


class SettingsDialog(QDialog):
    settings_changed = Signal()

    PAGE_CREDENTIALS = 0
    PAGE_UI          = 1
    PAGE_LOGGING     = 2
    PAGE_ABOUT       = 3

    def __init__(self, parent=None, start_page: int = PAGE_CREDENTIALS):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(900, 500)
        center_window(self)

        self._nav = QListWidget()
        self._nav.setObjectName("settings-nav")
        self._nav.setFixedWidth(150)
        self._nav.setSpacing(2)
        for label in ("Credentials", "UI Settings", "Logging", "About"):
            item = QListWidgetItem(label)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._nav.addItem(item)

        self._pages = QStackedWidget()
        self.creds_page   = CredentialsPage()
        self.ui_page      = UISettingsPage()
        self.logging_page = LoggingPage()
        self.about_page   = AboutPage()
        for page in (self.creds_page, self.ui_page, self.logging_page, self.about_page):
            self._pages.addWidget(page)

        self._nav.currentRowChanged.connect(self._pages.setCurrentIndex)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        content = QHBoxLayout()
        content.addWidget(self._nav)
        content.addWidget(self._pages, 1)

        root = QVBoxLayout(self)
        root.addLayout(content, 1)
        root.addWidget(buttons)

        self._nav.setCurrentRow(start_page)

    def _save(self):
        try:
            self.creds_page.save()
            self.ui_page.save()
            self.logging_page.save()
            self.settings_changed.emit()
            self.accept()
        except ValueError as e:
            show_error_dialog(f"Validation error: {e}")
        except Exception as e:
            show_error_dialog(f"Error saving settings: {e}", show_traceback=True)