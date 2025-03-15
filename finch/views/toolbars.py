import functools
import finch.resources
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import QWidget, QSizePolicy, QToolBar
from PyQt5.QtWidgets import QToolBar, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

from finch.controllers.download import download_files
from finch.controllers.file_actions import global_create, global_delete
from finch.controllers.search import search
from finch.controllers.upload import upload_file
from finch.services.s3_service import ObjectType
from finch.views.about import AboutWindow
from finch.views.credentials import ManageCredentialsWindow

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from finch.views.main_window import MainWindow


class CredentialsToolbar(QToolBar):
    def __init__(self, parent):
        super().__init__("Credentials", parent)
        self.parent = parent  # Reference to main window
        self.init_ui()

    def init_ui(self):
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.manage_credentials_action = QAction("Manage Credentials", self)
        self.manage_credentials_action.setIcon(QIcon(':/icons/new-credential.svg'))
        self.manage_credentials_action.triggered.connect(self.show_credentials_window)
        self.addAction(self.manage_credentials_action)

    def show_credentials_window(self):
        self.parent.manage_credential_window = ManageCredentialsWindow()
        self.parent.manage_credential_window.window_closed.connect(
            functools.partial(self.parent._fill_credentials, self.parent.credential_selector.currentIndex()))
        self.parent.manage_credential_window.show()


class SettingsToolbar(QToolBar):
    def __init__(self, parent):
        super().__init__("Settings", parent)
        self.parent = parent  # Reference to main window
        self.init_ui()

    def init_ui(self):
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.show_settings_action = QAction("Settings", self)
        self.show_settings_action.setIcon(QIcon(':/icons/settings.svg'))
        self.show_settings_action.triggered.connect(self.show_about_window)
        self.show_about_action = QAction("About", self)
        self.show_about_action.setIcon(QIcon(':/icons/about.svg'))
        self.show_about_action.triggered.connect(self.show_about_window)
        self.addWidget(spacer)
        self.addAction(self.show_settings_action)
        self.addAction(self.show_about_action)


    def show_about_window(self):
        self.parent.about_window = AboutWindow()
        self.parent.about_window.show()


class FileToolbar(QToolBar):
    def __init__(self, parent):
        super().__init__("File", parent)
        self.parent = parent  # Reference to main window

        # Note: Passing actual method references instead of strings.
        self.action_list = [
            ("Upload", ':/icons/upload.svg', upload_file, True),
            ("Create", ':/icons/new-folder.svg', lambda: global_create(self.parent.s3_tree), True),
            ("Delete", ':/icons/trash.svg', global_delete, True),
            ("Download", ':/icons/download.svg', download_files, True),
            ("Refresh", ':/icons/refresh.svg', self.parent._refresh_ui, True),
            ("Search", ':/icons/search.svg', search, True)
        ]

        # Dictionary to hold QAction references for dynamic updates
        self.actions_dict = {}
        self.init_ui()

        # Set initial state
        self.update_all_actions({
            "Upload": False,
            "Create": True,  # Can always create buckets
            "Delete": False,
            "Download": False,
            "Refresh": True,
            "Search": True
        })

    def connect_tree_signals(self, tree_view):
        """Connect to tree view signals after tree is available"""
        if tree_view:
            tree_view.item_selected.connect(self._handle_single_selection)
            tree_view.items_selected.connect(self._handle_multiple_selection)

    def _handle_single_selection(self, node):
        """Handle single item selection"""
        if node is None:
            # No selection
            self.update_all_actions({
                "Upload": False,
                "Create": True,  # Can always create buckets
                "Delete": False,
                "Download": False,
                "Refresh": True,
                "Search": True
            })
        elif node.type == ObjectType.BUCKET:
            self.update_all_actions({
                "Upload": True,  # Can upload to bucket
                "Create": True,  # Can create folder in bucket
                "Delete": True,  # Can delete bucket
                "Download": False,  # Can't download bucket
                "Refresh": True,
                "Search": True
            })
        elif node.type == ObjectType.FOLDER:
            self.update_all_actions({
                "Upload": True,  # Can upload to folder
                "Create": True,  # Can create subfolder
                "Delete": True,  # Can delete folder
                "Download": False,  # Can't download folder
                "Refresh": True,
                "Search": True
            })
        else:  # FILE
            self.update_all_actions({
                "Upload": False,  # Can't upload to file
                "Create": False,  # Can't create in file
                "Delete": True,  # Can delete file
                "Download": True,  # Can download file
                "Refresh": True,
                "Search": True
            })

    def _handle_multiple_selection(self, nodes):
        """Handle multiple item selection"""
        all_same_type = len(set(node.type for node in nodes)) == 1
        self.update_all_actions({
            "Upload": False,  # Can't upload with multiple selection
            "Create": False,  # Can't create with multiple selection
            "Delete": all_same_type,  # Can only delete if all same type
            "Download": True,  # Can download multiple items
            "Refresh": True,
            "Search": True
        })

    def init_ui(self):
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for text, icon_path, handler, initially_disabled in self.action_list:
            # Create the action with icon and text
            action = QAction(QIcon(icon_path), text, self)
            action.triggered.connect(handler)  # Connect the provided callable
            action.setDisabled(initially_disabled)
            self.addAction(action)
            # Save the action in the dictionary for later reference
            self.actions_dict[text] = action

    # Method to dynamically update an action's enabled status
    def set_action_enabled(self, action_name: str, enabled: bool):
        """
        Enable or disable a toolbar action by its display text.
        """
        if action_name in self.actions_dict:
            self.actions_dict[action_name].setEnabled(enabled)
        else:
            print(f"Action '{action_name}' not found!")

    # Alternatively, if you want to update all actions at once:
    def update_all_actions(self, enable_map: dict):
        """
        Update multiple actions' enabled statuses.
        enable_map should be a dict with keys as action texts and values as booleans.
        """
        for action_name, status in enable_map.items():
            self.set_action_enabled(action_name, status)


def init_main_toolbars(window: "MainWindow") -> None:
    window.credentials_toolbar = CredentialsToolbar(window)
    window.file_toolbar = FileToolbar(window)
    window.about_toolbar = SettingsToolbar(window)
    window.addToolBar(window.credentials_toolbar)
    window.addToolBar(window.file_toolbar)
    window.addToolBar(window.about_toolbar)
