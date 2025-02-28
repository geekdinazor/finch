from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QComboBox,
    QHBoxLayout, QApplication
)

from finch.services.s3_service import S3Service
from finch.utils.config import get_credentials_names, get_credential_by_name
from finch.utils.ui import center_window
from finch.views.error import show_error_dialog
from finch.views.toolbars import init_main_toolbars
from finch.widgets.file_tree_widget import S3TreeViewFactory
from finch.widgets.progress_indicator import QProgressIndicator


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Finch S3 Client")
        self.resize(1200, 700)
        center_window(self)

        # Initialize UI elements
        self.credentials_toolbar = None
        self.file_toolbar = None
        self.about_toolbar = None
        self.credential_selector = None
        self.s3_tree = None
        self.s3_service = None
        
        # Initialize spinner
        self.spinner = QProgressIndicator(self)

        # Setup main layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignTop)
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.setup_ui()

    def _show_filetree(self):
        try:
            if self.s3_tree is None:
                if self.s3_service is None:
                    self.s3_service = S3Service()
                
                # Use factory to create tree view
                self.s3_tree = S3TreeViewFactory.create(
                    parent=self.main_widget,
                    s3_service=self.s3_service
                )
                
                # Connect signals and add to layout
                self.s3_tree.error_occurred.connect(self._handle_tree_error)
                self.s3_tree.context_menu_open.connect(self._handle_context_menu)
                self.s3_tree.loading_started.connect(self.start_loading)
                self.s3_tree.loading_finished.connect(self.stop_loading)
                
                # Connect toolbar signals
                self.file_toolbar.connect_tree_signals(self.s3_tree)
                
                self.main_layout.addWidget(self.s3_tree)
                
            return self.s3_tree
        except Exception as e:
            print(f"Error in _show_filetree: {str(e)}")
            return None

    def _handle_tree_error(self, error_message: str):
        """Handle errors from the tree view"""
        print(f"Tree Error: {error_message}")
        # You might want to show an error dialog here

    def _handle_context_menu(self, pos):
        indexes = self.s3_tree.selectedIndexes()
        print(indexes)


    def on_credential_selected(self, index: int):
        if index <= 0:
            return
            
        try:
            cred_name = self.credential_selector.currentText()
            cred_data = get_credential_by_name(cred_name)
            if not cred_data:
                return

            # Create and configure service first
            if self.s3_service is None:
                self.s3_service = S3Service()
            self.s3_service.set_credential(cred_data)

            # Create tree view and refresh immediately
            tree_view = self._show_filetree()
            if tree_view:
                # Disconnect any existing connections
                try:
                    tree_view.loading_started.disconnect(self.start_loading)
                    tree_view.loading_finished.disconnect(self.stop_loading)
                except:
                    pass
                
                # Connect loading signals
                tree_view.loading_started.connect(self.start_loading)
                tree_view.loading_finished.connect(self.stop_loading)
                
                # Start refresh
                QTimer.singleShot(0, tree_view.refresh)
            
        except Exception as e:
            show_error_dialog(e, show_traceback=True)

    def _fill_credentials(self, selected_index=0):
        # Check if container already exists and remove it
        if hasattr(self, 'credentials_container'):
            self.main_layout.removeWidget(self.credentials_container)
            self.credentials_container.deleteLater()

        # Create container for credential selector and spinner
        self.credentials_container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.credentials_container.setLayout(layout)

        # Setup credential selector
        self.credential_selector = QComboBox()
        self.credential_selector.addItem("Select Credential", 0)
        self.credential_selector.addItems(get_credentials_names())
        self.credential_selector.setCurrentIndex(selected_index)
        self.credential_selector.currentIndexChanged.connect(self.on_credential_selected)
        
        # Add widgets to container
        layout.addWidget(self.credential_selector)
        layout.addWidget(self.spinner)

        # Add container to main layout
        self.main_layout.insertWidget(0, self.credentials_container)
        self._refresh_ui()

    def start_loading(self):
        """Start the loading spinner"""
        # print("start")
        self.spinner.start()
        QApplication.processEvents()  # Force UI update

    def stop_loading(self):
        """Stop the loading spinner"""
        self.spinner.stop()
        QApplication.processEvents()  # Force UI update

    def _refresh_tree(self, tree_view):
        try:
            tree_view.refresh()
        except Exception as e:
            print(f"Error in scheduled refresh: {str(e)}")

    def _refresh_ui(self):
        # Refresh UI elements if needed
        pass

    def setup_ui(self):
        # Init toolbars
        init_main_toolbars(self)
        self._fill_credentials()

