from PySide6 import QtCore
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QToolBar, QComboBox, QWidget, QSizePolicy, QLabel

from finch.config import ObjectType
from finch.utils.ui import resource_path


class CredentialsToolbar(QToolBar):
    def __init__(self, window):
        super().__init__("Credentials", window)
        self.window = window
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(resource_path("img/icon.png")).pixmap(QSize(36, 36)))
        icon_label.setContentsMargins(6, 0, 4, 0)
        self.addWidget(icon_label)

        self.credential_selector = QComboBox()
        self.addWidget(self.credential_selector)

    def populate(self, credential_names: list, selected_index: int = 0):
        self.credential_selector.blockSignals(True)
        self.credential_selector.clear()
        self.credential_selector.addItem("Select Credential", 0)
        self.credential_selector.addItems(credential_names)
        self.credential_selector.setCurrentIndex(selected_index)
        self.credential_selector.blockSignals(False)


class FileToolbar(QToolBar):
    def __init__(self, window):
        super().__init__("File", window)
        self.window = window
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)

        self.upload_action = QAction(self)
        self.upload_action.setText("&Upload")
        self.upload_action.setIcon(QIcon(resource_path('img/upload.svg')))
        self.upload_action.triggered.connect(window.upload_file)
        self.upload_action.setDisabled(True)

        self.create_action = QAction(self)
        self.create_action.setText("&Create")
        self.create_action.setIcon(QIcon(resource_path('img/new-folder.svg')))
        self.create_action.triggered.connect(window.create)

        self.delete_action = QAction(self)
        self.delete_action.setText("&Delete")
        self.delete_action.setIcon(QIcon(resource_path('img/trash.svg')))
        self.delete_action.triggered.connect(window.delete)
        self.delete_action.setDisabled(True)

        self.download_action = QAction(self)
        self.download_action.setText("&Download")
        self.download_action.setIcon(QIcon(resource_path('img/download.svg')))
        self.download_action.triggered.connect(window.download_files)
        self.download_action.setDisabled(True)

        self.refresh_action = QAction(self)
        self.refresh_action.setText("&Refresh")
        self.refresh_action.setIcon(QIcon(resource_path('img/refresh.svg')))
        self.refresh_action.triggered.connect(window.refresh)

        self.search_action = QAction(self)
        self.search_action.setText("&Search")
        self.search_action.setIcon(QIcon(resource_path('img/search.svg')))
        self.search_action.triggered.connect(window.search)

        for action in (self.upload_action, self.create_action, self.delete_action,
                       self.download_action, self.refresh_action, self.search_action):
            self.addAction(action)

    def update_state(self, rows: list):
        """Enable/disable actions based on the current tree selection."""
        if not rows:
            self.upload_action.setDisabled(True)
            self.create_action.setDisabled(False)
            self.delete_action.setDisabled(True)
            self.download_action.setDisabled(True)
            self.refresh_action.setDisabled(False)
            self.search_action.setDisabled(False)
            return

        def node_type(index):
            node = index.data(0x100)  # Qt.UserRole
            return node.s3_object.type if node else None

        all_files = all(node_type(r) == ObjectType.FILE for r in rows)
        single = len(rows) == 1
        first_type = node_type(rows[0])

        if all_files:
            self.upload_action.setDisabled(True)
            self.create_action.setDisabled(True)
            self.delete_action.setDisabled(False)
            self.download_action.setDisabled(False)
            self.refresh_action.setDisabled(False)
            self.search_action.setDisabled(False)
        elif single and first_type in (ObjectType.BUCKET, ObjectType.FOLDER):
            self.upload_action.setDisabled(False)
            self.create_action.setDisabled(False)
            self.delete_action.setDisabled(False)
            self.download_action.setDisabled(True)
            self.refresh_action.setDisabled(False)
            self.search_action.setDisabled(False)
        else:
            self.upload_action.setDisabled(True)
            self.create_action.setDisabled(False)
            self.delete_action.setDisabled(True)
            self.download_action.setDisabled(True)
            self.refresh_action.setDisabled(False)
            self.search_action.setDisabled(False)

    def disable_search(self):
        self.search_action.setDisabled(True)

    def enable_search(self):
        self.search_action.setDisabled(False)


class SettingsToolbar(QToolBar):
    def __init__(self, window):
        super().__init__("Settings", window)
        self.window = window
        self.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer)

        settings_action = QAction(self)
        settings_action.setText("&Settings")
        settings_action.setIcon(QIcon(resource_path('img/settings.svg')))
        settings_action.triggered.connect(window.open_settings)
        self.addAction(settings_action)

        about_action = QAction(self)
        about_action.setText("&About")
        about_action.setIcon(QIcon(resource_path('img/about.svg')))
        about_action.triggered.connect(window.open_about_window)
        self.addAction(about_action)


def init_toolbars(window) -> tuple:
    """
    Create and attach all three toolbars to *window*.
    Returns (credentials_toolbar, file_toolbar, settings_toolbar).
    """
    creds_tb = CredentialsToolbar(window)
    file_tb = FileToolbar(window)
    settings_tb = SettingsToolbar(window)

    window.addToolBar(creds_tb)
    window.addToolBar(file_tb)
    window.addToolBar(settings_tb)

    return creds_tb, file_tb, settings_tb
