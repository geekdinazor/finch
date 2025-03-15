from typing import TYPE_CHECKING

from PyQt5 import QtCore
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTreeView, QHeaderView, QApplication, QMenu, QAction
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from finch.controllers.download import download_files
from finch.controllers.file_actions import global_create, global_delete
from finch.controllers.tools import show_cors_window, show_acl_window, show_presigned_url
from finch.controllers.upload import upload_file
from finch.models.file_tree_model import S3FileTreeModel, S3Node
from finch.services.s3_service import ObjectType

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from finch.views.main_window import MainWindow


class S3TreeViewFactory:
    @staticmethod
    def create(parent, s3_service):
        """Factory method to create S3TreeView safely"""
        # Ensure we're in the main thread
        if not QApplication.instance().thread() == QApplication.instance().thread():
            raise RuntimeError("Must create S3TreeView in main thread")
            
        view = S3TreeView(parent)
        view.setup(s3_service)
        return view

class S3TreeView(QTreeView):
    item_selected = pyqtSignal(S3Node)
    items_selected = pyqtSignal(list)
    context_menu_open = pyqtSignal(QtCore.QPoint)
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()
    loading_finished = pyqtSignal()
    selection_changed = pyqtSignal(dict)  # New signal for toolbar states

    def __init__(self, parent=None):
        super().__init__(parent)
        self._s3_service = None
        self.model = None
        self._setup_ui()
        
        # Connect expansion signal
        self.expanded.connect(self._handle_expansion)

    def setup(self, s3_service):
        """Setup the tree view with an S3 service"""
        self._s3_service = s3_service
        self._safe_initialize_model()
        if self.model:
            self.model.tree_view = self  # Give model access to view

    def _setup_ui(self):
        """Configure the tree view"""
        # Enable selection
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setSelectionBehavior(QTreeView.SelectRows)
        
        # Create custom_menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._handle_context_menu)
        
        # Enable sorting
        self.setSortingEnabled(True)
        
        # Enable expansion
        self.setExpandsOnDoubleClick(True)
        self.setItemsExpandable(True)

    def _setup_header(self):
        """Setup header after model is set"""
        if self.header():
            self.header().setSectionResizeMode(0, QHeaderView.Stretch)
            self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            self.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            self.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
            self.header().setStretchLastSection(False)
    def _safe_initialize_model(self):
        """Initialize model safely in the main thread"""
        try:
            if self._s3_service is None:
                self.error_occurred.emit("S3 service not provided")
                return

            self.model = S3FileTreeModel(self, self._s3_service)
            
            # Connect model signals
            self.model.error_occurred.connect(self._handle_error)
            self.model.loading_started.connect(self.loading_started)
            self.model.loading_finished.connect(self.loading_finished)
            
            self.setModel(self.model)
            self._setup_header()
            
            # Connect selection signals after model is set
            self._connect_signals()
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize model: {str(e)}")

    def _connect_signals(self):
        """Connect selection signals"""
        if self.model and self.selectionModel():
            self.selectionModel().selectionChanged.connect(self._handle_selection)
            self.model.error_occurred.connect(self._handle_error)

    def _handle_selection(self, selected, deselected):
        """Handle selection changes"""
        selected_indexes = self.selectionModel().selectedRows()
        selected_count = len(selected_indexes)

        if selected_count == 1:
            node = self.model.get_node(selected_indexes[0])
            self.item_selected.emit(node)
        elif selected_count > 1:
            nodes = [self.model.get_node(idx) for idx in selected_indexes]
            self.items_selected.emit(nodes)
        else:
            # No selection - emit None for item_selected
            self.item_selected.emit(None)

    def _handle_context_menu(self, pos):
        """Handle context menu requests"""
        menu = QMenu()
        action_list = []
        tool_list = []
        selected_indexes = self.selectionModel().selectedRows()
        if len(selected_indexes) == 1:
            actions = {
                ObjectType.BUCKET: [
                    ("Upload", ':/icons/upload.svg', upload_file),
                    ("Create Folder", ':/icons/new-folder.svg', lambda: global_create(self)),
                    ("Delete Bucket", ':/icons/trash.svg', lambda: global_delete(self))
                ],
                ObjectType.FOLDER: [
                    ("Upload", ':/icons/upload.svg', upload_file),
                    ("Create Folder", ':/icons/new-folder.svg', lambda: global_create(self)),
                    ("Delete Folder", ':/icons/trash.svg', lambda: global_delete(self))
                ],
                ObjectType.FILE: [
                    ("Download File", ':/icons/download.svg', download_files),
                    ("Delete File", ':/icons/trash.svg', lambda: global_delete(self))
                ]
            }

            tools = {
                ObjectType.BUCKET: [
                    ("CORS Configurations", ':/icons/globe.svg', show_cors_window),
                    ("ACL Configurations", ':/icons/settings.svg', show_acl_window)
                ],
                ObjectType.FILE: [
                    ("Get Presigned URL", ':/icons/globe.svg', show_presigned_url)
                ]
            }

            node = self.model.get_node(selected_indexes[0])
            action_list = actions.get(node.type)
            tool_list = tools.get(node.type)

        elif len(selected_indexes) > 1:
            nodes = [self.model.get_node(idx) for idx in selected_indexes]
            selected_object_types = set(map(lambda n: n.type, nodes))
            if len(selected_object_types) == 1:
                action_list = [
                    ("Delete", ':/icons/trash.svg', lambda: global_delete(self)),
                ]

        for action_name, icon_path, callback in action_list:
            action = QAction(QIcon(icon_path), action_name, self)
            if callback:
                action.triggered.connect(callback)
            else:
                QMenu(action_name)
            menu.addAction(action)

        if tool_list:
            tools_menu = menu.addMenu("Tools")
            tools_menu.setIcon(QIcon(':/icons/tools.svg'))
            for tool_name, icon_path, callback in tool_list:
                action = QAction(QIcon(icon_path), tool_name, self)
                if callback:
                    action.triggered.connect(callback)
                else:
                    QMenu(tool_name)
                tools_menu.addAction(action)


        menu.exec_(self.viewport().mapToGlobal(pos))



    def _handle_error(self, error_message: str):
        """Handle model errors"""
        print(f"S3TreeView Error: {error_message}")
        self.error_occurred.emit(error_message)

    def refresh(self):
        """Refresh the tree view"""
        try:
            self.loading_started.emit()
            if not self.model:
                QTimer.singleShot(100, self.refresh)
                return
            
            if not hasattr(self.model, 'load_buckets'):
                return
            
            # Connect model signals
            if hasattr(self.model, 'error_occurred'):
                try:
                    self.model.error_occurred.disconnect(self._handle_error)
                except:
                    pass
                self.model.error_occurred.connect(self._handle_error)
            
            if hasattr(self.model, 'loading_finished'):
                try:
                    self.model.loading_finished.disconnect(self.loading_finished)
                except:
                    pass
                self.model.loading_finished.connect(self.loading_finished)
            
            # Start loading in background
            self.model.load_buckets()
            
        except Exception as e:
            self._handle_error(f"Failed to refresh: {str(e)}")
            self.loading_finished.emit()

    def _handle_expansion(self, index):
        """Handle item expansion"""
        if not self.model:
            return
        
        node = self.model.get_node(index)
        if not node:
            return
        
        # If node already has children, no need to check or fetch
        if len(node.children) > 0:
            return
        
        # If node is not a bucket or folder, nothing to do
        if node.type not in (ObjectType.BUCKET, ObjectType.FOLDER):
            return
        
        # Start loading
        self.loading_started.emit()
        
        # If we know it has no children, collapse it back
        node_id = id(node)
        if node_id in self.model._has_children_cache:
            if not self.model._has_children_cache[node_id]:
                self.collapse(index)
                return
        
        # Directly fetch children without checking
        self.model._fetch_children(node, index)

    def collapse(self, index):
        """Override collapse to handle empty nodes"""
        super().collapse(index)
        # Force a visual update
        if self.model:
            self.model.dataChanged.emit(
                index,
                self.model.index(index.row(), self.model.columnCount(index.parent())-1, index.parent())
            )

    def _on_item_expanded(self, index):
        """Debug handler for item expansion"""
        if self.model:
            node = self.model.get_node(index)
            print(f"\nDEBUG: Item expanded: {node.name} ({node.type})")

    def _on_item_collapsed(self, index):
        """Debug handler for item collapse"""
        if self.model:
            node = self.model.get_node(index)
            print(f"\nDEBUG: Item collapsed: {node.name} ({node.type})")