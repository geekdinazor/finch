from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, List
import uuid

from PyQt5.QtCore import (
    Qt, QAbstractItemModel, QModelIndex,
    QVariant, pyqtSignal, QThread, QRunnable, QThreadPool, QMetaObject, QObject, pyqtSlot, QMutex, QWaitCondition, QMutexLocker, Q_ARG
)
from PyQt5.QtWidgets import QStyle, QApplication
from PyQt5 import QtCore

from finch.services.s3_service import S3Object, ObjectType
from finch.utils.strings import format_datetime, format_size
from finch.config import CHECK_FOLDER_CONTENTS


@dataclass
class S3Node(S3Object):
    """Node representing an S3 object in the tree"""
    # Tree structure
    parent: Optional['S3Node'] = None
    children: List['S3Node'] = field(default_factory=list)
    is_loaded: bool = False
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID for each node

    def can_fetch_more(self) -> bool:
        """Check if this node can fetch more children"""
        return not self.is_loaded and self.type in (ObjectType.BUCKET, ObjectType.FOLDER)


class S3ObjectLoaderThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, s3_service, parent_node=None, bucket=None, prefix=None):
        super().__init__()
        self._s3_service = s3_service
        self._parent_node = parent_node
        self._bucket = bucket
        self._prefix = prefix
        self._is_running = False

    def _create_node(self, obj: S3Object, parent: S3Node) -> S3Node:
        """Create a node from S3Object"""
        obj_dict = obj.__dict__.copy()
        if 'parent' in obj_dict:
            del obj_dict['parent']
        return S3Node(**obj_dict, parent=parent)

    def _list_objects(self):
        """Get objects from S3 in a separate thread"""
        items = []
        for item in self._s3_service.list_objects(self._bucket, self._prefix or ""):
            if not self._is_running:
                break
            items.append(item)
        return items

    def stop(self):
        """Safely stop the thread"""
        self._is_running = False
        self.wait()  # Wait for thread to finish

    def run(self):
        if self._is_running:
            return
            
        self._is_running = True
        try:
            if self._bucket is None:
                # Load buckets in thread
                if self._is_running:  # Check if still running
                    items = self._s3_service.list_buckets()
                    if self._is_running:  # Check again before processing
                        nodes = [self._create_node(item, self._parent_node) for item in items]
            else:
                # Load objects in thread
                items = self._list_objects()  # This runs in the worker thread
                if self._is_running:
                    nodes = [self._create_node(item, self._parent_node) for item in items]

            if self._is_running:
                self.finished.emit(nodes)
                
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))
        finally:
            self._is_running = False


class S3ChildrenCheckerWorker(QRunnable):
    def __init__(self, s3_service, node_id, node, callback):
        super().__init__()
        self._s3_service = s3_service
        self._node_id = node_id
        self._node = node
        self._callback = callback
        self._is_running = True
        
    def stop(self):
        self._is_running = False
        
    def run(self):
        try:
            if not self._is_running:
                return
                
            # Use thread-local client
            client = self._s3_service.client
            
            has_children = False
            if self._node.type == ObjectType.BUCKET:
                response = client.list_objects_v2(
                    Bucket=self._node.name,
                    MaxKeys=1,
                    Delimiter='/'
                )
                has_children = ('Contents' in response or 'CommonPrefixes' in response)
            else:
                # For folders, we need to check beyond the folder marker
                response = client.list_objects_v2(
                    Bucket=self._node.bucket,
                    Prefix=f"{self._node.key}/",
                    MaxKeys=2,  # Get one more to look past the folder marker
                    Delimiter='/'
                )
                
                has_children = False
                if 'Contents' in response:
                    # Check for any files beyond the folder marker
                    for obj in response['Contents']:
                        if obj['Key'] != f"{self._node.key}/":  # Skip folder marker
                            has_children = True
                            break
                
                # Also check for subfolders
                if 'CommonPrefixes' in response:
                    has_children = True
                
                # If we only found the folder marker and nothing else
                if len(response.get('Contents', [])) == 1 and not response.get('CommonPrefixes'):
                    only_obj = response['Contents'][0]
                    if only_obj['Key'] == f"{self._node.key}/":
                        has_children = False
            
            if self._is_running:
                QMetaObject.invokeMethod(self._callback, 
                                       "handle_result",
                                       QtCore.Qt.QueuedConnection,
                                       QtCore.Q_ARG(str, self._node_id),
                                       QtCore.Q_ARG(bool, has_children))
        except Exception as e:
            print(f"Error checking children: {str(e)}")
            if self._is_running:
                QMetaObject.invokeMethod(self._callback,
                                       "handle_error",
                                       QtCore.Qt.QueuedConnection,
                                       QtCore.Q_ARG(str, self._node_id))


class S3ChildrenCheckerCallback(QObject):
    finished = pyqtSignal(str, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = True
    
    def stop(self):
        self._active = False
    
    @pyqtSlot(str, bool)
    def handle_result(self, node_id, has_children):
        if self._active:
            self.finished.emit(node_id, has_children)
        
    @pyqtSlot(str)
    def handle_error(self, node_id):
        if self._active:
            self.finished.emit(node_id, False)


class S3FileTreeModel(QAbstractItemModel):
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()  # Add loading_started signal
    loading_finished = pyqtSignal()

    # Column indices
    NAME, TYPE, SIZE, MODIFIED = range(4)

    def __init__(self, parent=None, s3_service=None):
        super().__init__(parent)
        self._s3_service = s3_service
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(4)  # Limit concurrent threads
        
        self.root = S3Node(
            name="",
            type=ObjectType.FOLDER,
            parent=None
        )
        
        self._setup_icons()
        self._current_worker = None
        self._has_children_cache = {}
        self._checking_nodes = set()
        self._checker_callback = S3ChildrenCheckerCallback(self)
        self._checker_callback.finished.connect(self._on_children_checked)
        self._active_checkers = {}
        self._node_map = {}  # Add node map to track nodes by ID

    def _setup_icons(self):
        """Setup model icons"""
        self._icons = {
            'Bucket': QApplication.style().standardIcon(QStyle.SP_DriveNetIcon),
            'Folder': QApplication.style().standardIcon(QStyle.SP_DirIcon),
            'File': QApplication.style().standardIcon(QStyle.SP_FileIcon)
        }

    @property
    def s3_service(self):
        return self._s3_service

    @s3_service.setter
    def s3_service(self, value):
        self._s3_service = value

    def _create_node_from_s3object(self, obj: S3Object, parent: S3Node) -> S3Node:
        """Create a node from S3Object"""
        obj_dict = obj.__dict__.copy()
        if 'parent' in obj_dict:
            del obj_dict['parent']  # Remove parent from dict if present
        return S3Node(
            **obj_dict,
            parent=parent
        )

    def _cleanup_worker(self):
        """Clean up current worker thread"""
        if self._current_worker:
            try:
                self._current_worker.stop()  # Use new stop method
                self._current_worker.finished.disconnect()
                self._current_worker.error.disconnect()
                self._current_worker.quit()
                if not self._current_worker.wait(1000):  # Wait up to 1 second
                    self._current_worker.terminate()
                self._current_worker.deleteLater()
            except:
                pass
            self._current_worker = None

    def load_buckets(self) -> None:
        """Load top-level buckets in background"""
        try:
            if not self._s3_service:
                self.error_occurred.emit("S3 service not provided")
                self.loading_finished.emit()
                return

            self.loading_started.emit()
            self.beginResetModel()
            self.root.children.clear()

            # Clean up any existing worker
            self._cleanup_worker()

            # Create and start new worker with parent node
            self._current_worker = S3ObjectLoaderThread(
                self._s3_service,
                parent_node=self.root
            )
            self._current_worker.finished.connect(
                lambda nodes: self._on_nodes_loaded(nodes, self.root, QModelIndex())
            )
            self._current_worker.error.connect(self._on_load_error)
            self._current_worker.start()

        except Exception as e:
            self.error_occurred.emit(f"Failed to start loading buckets: {str(e)}")
            self.loading_finished.emit()
            self.endResetModel()

    def _on_nodes_loaded(self, nodes, parent_node, parent_index):
        """Handle loaded nodes"""
        try:
            # Store nodes in map
            for node in nodes:
                self._node_map[node.node_id] = node
                
            # Rest of the loading code...
            self.beginInsertRows(parent_index, 0, len(nodes) - 1)
            parent_node.children = nodes
            parent_node.is_loaded = True
            self.endInsertRows()
            
            self.loading_finished.emit()
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.loading_finished.emit()

    def _fetch_children(self, parent_node: S3Node, parent_index: QModelIndex) -> None:
        try:
            if not self._s3_service:
                self.error_occurred.emit("S3 service not provided")
                self.loading_finished.emit()
                return

            # Get bucket and prefix
            if parent_node.type == ObjectType.BUCKET:
                bucket = parent_node.name
                prefix = ""
            else:  # FOLDER
                bucket = parent_node.bucket
                prefix = f"{parent_node.key}/"

            # Clean up any existing worker
            self._cleanup_worker()

            # Create and start new worker with parent node
            self._current_worker = S3ObjectLoaderThread(
                self._s3_service, 
                parent_node=parent_node,
                bucket=bucket, 
                prefix=prefix
            )
            self._current_worker.finished.connect(
                lambda nodes: self._on_nodes_loaded(nodes, parent_node, parent_index)
            )
            self._current_worker.error.connect(self._on_load_error)
            self._current_worker.start()

        except Exception as e:
            self.error_occurred.emit(f"Failed to start fetching children: {str(e)}")
            parent_node.is_loaded = False
            self.loading_finished.emit()

    def canFetchMore(self, parent: QModelIndex) -> bool:
        """Check if more data can be fetched for the given index"""
        if not parent.isValid():
            return False

        node = self.get_node(parent)
        node_id = node.node_id
        
        # If we're still checking for children, wait
        if node_id in self._checking_nodes:
            return False
            
        # If we know it has no children from cache, don't fetch
        if node_id in self._has_children_cache and not self._has_children_cache[node_id]:
            return False
            
        return node.can_fetch_more()

    def fetchMore(self, parent: QModelIndex) -> None:
        """Fetch child items for the given index"""
        if not parent.isValid():
            return

        node = self.get_node(parent)
        node_id = node.node_id
        
        # If we're still checking for children, don't fetch yet
        if node_id in self._checking_nodes:
            return
            
        # If we know it has no children from cache, don't fetch
        if node_id in self._has_children_cache and not self._has_children_cache[node_id]:
            return
            
        if not node.can_fetch_more():
            return

        try:
            self.loading_started.emit()
            self._fetch_children(node, parent)
        except Exception as e:
            self.error_occurred.emit(f"Failed to fetch contents: {str(e)}")
            self.loading_finished.emit()

    def get_node(self, index: QModelIndex) -> Optional[S3Node]:
        """Get S3Node from model index"""
        if not index.isValid():
            return self.root
        return index.internalPointer()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_node = self.get_node(parent)
        child_node = parent_node.children[row]
        return self.createIndex(row, column, child_node)

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get parent index of the given index"""
        if not index.isValid():
            return QModelIndex()

        try:
            node = self.get_node(index)
            if not node:
                return QModelIndex()
            
            # Check if node has parent attribute
            if not hasattr(node, 'parent'):
                return QModelIndex()
            
            parent_node = node.parent
            if not parent_node or parent_node == self.root:
                return QModelIndex()

            # Find parent's row number
            grandparent = getattr(parent_node, 'parent', None)
            if not grandparent:
                return QModelIndex()
        
            try:
                row = grandparent.children.index(parent_node)
                return self.createIndex(row, 0, parent_node)
            except (ValueError, AttributeError):
                return QModelIndex()
            
        except Exception:
            return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        node = self.get_node(parent)
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 4  # Name, Type, Size, Modified

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return QVariant()

        node = self.get_node(index)
        column = index.column()

        if role == Qt.DisplayRole:
            if column == self.NAME:
                return node.name
            elif column == self.TYPE:
                return node.type.value
            elif column == self.SIZE:
                return format_size(node.size)
            elif column == self.MODIFIED:
                return format_datetime(node.last_modified)

        elif role == Qt.TextAlignmentRole:
            if column == self.SIZE:
                return Qt.AlignLeft | Qt.AlignVCenter


        elif role == Qt.DecorationRole and column == self.NAME:
            return self._icons.get(node.type.value)


        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return {
                self.NAME: "Name",
                self.TYPE: "Type",
                self.SIZE: "Size",
                self.MODIFIED: "Last Modified"
            }.get(section, "")
        return QVariant()

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder):
        """Sort the model by column"""
        self.layoutAboutToBeChanged.emit()
        
        def sort_children(children):
            if not children:
                return
                
            reverse = order == Qt.DescendingOrder
            if column == self.NAME:
                children.sort(key=lambda x: x.name.lower(), reverse=reverse)
            elif column == self.TYPE:
                children.sort(key=lambda x: x.type.value, reverse=reverse)
            elif column == self.SIZE:
                children.sort(key=lambda x: x.size, reverse=reverse)
            elif column == self.MODIFIED:
                children.sort(key=lambda x: x.last_modified or datetime.min, reverse=reverse)
                
            # Sort recursively
            for child in children:
                sort_children(child.children)
        
        sort_children(self.root.children)
        self.layoutChanged.emit()

    def _cleanup_checkers(self):
        """Clean up all checker threads"""
        # Stop all active checkers
        for checker in self._active_checkers.values():
            checker.stop()
            
        self._thread_pool.clear()
        self._thread_pool.waitForDone(100)
        
        self._active_checkers.clear()
        self._has_children_cache.clear()
        self._checking_nodes.clear()
        
        # Only delete callback if it exists and hasn't been deleted
        if hasattr(self, '_checker_callback') and not self._checker_callback.parent():
            try:
                self._checker_callback.deleteLater()
            except RuntimeError:
                pass  # Object already deleted
        self._checker_callback = None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return item flags for the given index"""
        if not index.isValid():
            return Qt.NoItemFlags

        node = self.get_node(index)
        node_id = node.node_id
        
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        
        # Only allow expansion for nodes that can have children
        if node.type in (ObjectType.BUCKET, ObjectType.FOLDER):
            if CHECK_FOLDER_CONTENTS:
                # Check cache first
                if node_id in self._has_children_cache:
                    if self._has_children_cache[node_id]:
                        flags |= Qt.ItemIsDropEnabled
                elif not node.is_loaded:  # Not checked yet
                    flags |= Qt.ItemIsDropEnabled
            else:
                # If content checking is disabled, all folders are expandable
                flags |= Qt.ItemIsDropEnabled
        
        return flags

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return True
        
        node = self.get_node(parent)
        
        # If we already have children, return True
        if len(node.children) > 0:
            return True
        
        # If content checking is disabled, assume all folders/buckets have children
        if not CHECK_FOLDER_CONTENTS:
            return node.type in (ObjectType.BUCKET, ObjectType.FOLDER)
        
        # Check cache first
        if node.node_id in self._has_children_cache:
            return self._has_children_cache[node.node_id]
        
        # Only check for children if it's a bucket or folder
        if not node.is_loaded and node.type in (ObjectType.BUCKET, ObjectType.FOLDER):
            if node.node_id not in self._checking_nodes:
                self._checking_nodes.add(node.node_id)
                
                # Create and start worker
                worker = S3ChildrenCheckerWorker(self._s3_service, node.node_id, node, self._checker_callback)
                self._active_checkers[node.node_id] = worker
                self._thread_pool.start(worker)
            
            # Return True while checking
            return True
        
        return False

    def _on_children_checked(self, node_id, has_children):
        """Handle completion of children check"""
        try:
            self._has_children_cache[node_id] = has_children
            self._checking_nodes.discard(node_id)
            
            # Clean up the checker
            if node_id in self._active_checkers:
                del self._active_checkers[node_id]
            
            # Get node from map
            node = self._node_map.get(node_id)
            if node:
                # Find the node's index
                parent = node.parent or self.root
                row = parent.children.index(node)
                
                # Create indexes - parent_index is based on parent's parent
                if parent == self.root:
                    parent_index = QModelIndex()
                else:
                    grandparent = parent.parent or self.root
                    parent_row = grandparent.children.index(parent)
                    parent_index = self.createIndex(parent_row, 0, parent)
                    
                node_index = self.createIndex(row, 0, node)
                
                if not has_children:
                    # Mark as loaded to prevent further checks
                    node.is_loaded = True
                    
                    # If expanded, collapse it
                    if hasattr(self, 'tree_view'):
                        self.tree_view.collapse(node_index)
                        # Force the view to refresh this item
                        self.tree_view.update(node_index)
                
                # Emit dataChanged for this node to update its appearance
                self.dataChanged.emit(
                    node_index,
                    self.index(node_index.row(), self.columnCount(parent_index)-1, parent_index)
                )
                
                # Force layout update
                self.layoutChanged.emit()
                
                # If node is expanded and has children, fetch them
                if has_children and hasattr(self, 'tree_view') and self.tree_view.isExpanded(node_index):
                    self._fetch_children(node, node_index)
            
        except Exception as e:
            print(f"Error in _on_children_checked: {str(e)}")

    def isExpanded(self, index):
        """Check if index is expanded in the view"""
        if hasattr(self, 'tree_view'):
            return self.tree_view.isExpanded(index)
        return False

    def _on_load_error(self, error_msg: str):
        """Handle load errors"""
        self.error_occurred.emit(error_msg)
        self.loading_finished.emit()
        self._cleanup_worker()

    def clearNode(self, index):
        """Clear cached data for a node to force refresh"""
        if not index.isValid():
            return
        
        node = self.get_node(index)
        if node:
            # Clear children and cache
            node.children = []
            node.is_loaded = False
            node_id = node.node_id
            
            # Clean up any existing checker
            if node_id in self._checking_nodes:
                self._checking_nodes.discard(node_id)

    def removeRow(self, row, parent=None):
        """Remove a row from the model"""
        if not parent:
            parent = QModelIndex()
        
        self.beginRemoveRows(parent, row, row)
        
        # Get the parent node
        parent_node = self.get_node(parent)
        if parent_node is None:
            parent_node = self.root
        
        # Remove the child at the specified row
        if 0 <= row < len(parent_node.children):
            del parent_node.children[row]
        
        self.endRemoveRows()
        return True

    def removeRows(self, row, count, parent=None):
        """Remove multiple rows from the model"""
        if not parent:
            parent = QModelIndex()
        
        self.beginRemoveRows(parent, row, row + count - 1)
        
        # Get the parent node
        parent_node = self.get_node(parent)
        if parent_node is None:
            parent_node = self.root
        
        # Remove the specified range of children
        del parent_node.children[row:row + count]
        
        self.endRemoveRows()
        return True

    def appendRow(self, parent_index, new_node):
        """Append a new node to the parent"""
        if not parent_index.isValid():
            parent_node = self.root
        else:
            parent_node = self.get_node(parent_index)
        
        if parent_node is None:
            return False
        
        # Set parent reference
        new_node.parent = parent_node
        
        # Check if node already exists
        for existing in parent_node.children:
            if existing.name == new_node.name and existing.type == new_node.type:
                return False
        
        # Add to parent's children
        row = len(parent_node.children)
        self.beginInsertRows(parent_index, row, row)
        parent_node.children.append(new_node)
        self.endInsertRows()
        
        return True

    def __del__(self):
        """Clean up when model is destroyed"""
        try:
            self._cleanup_checkers()
            self._cleanup_worker()
        except:
            pass  # Ignore cleanup errors during destruction