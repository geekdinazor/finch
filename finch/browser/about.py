from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

from finch.utils.ui import center_window, resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Finch")
        self.setFixedSize(360, 320)
        center_window(self)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(6)

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
        contributors_label.setContentsMargins(0, 12, 0, 0)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(version_label)
        layout.addWidget(contributors_label)
        for name in ["Furkan Kalkan <furkankalkan@mantis.com.tr>"]:
            layout.addWidget(QLabel(name))
        layout.addStretch()
        layout.addWidget(buttons)