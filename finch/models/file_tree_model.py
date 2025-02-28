from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, List

from PyQt5.QtCore import (
    Qt, QAbstractItemModel, QModelIndex,
    QVariant, pyqtSignal, QThread
)
from PyQt5.QtWidgets import QStyle, QApplication

from finch.services.s3_service import S3Object, ObjectType
from finch.utils.strings import format_datetime, format_size


@dataclass
class S3Node(S3Object):
    """Node representing an S3 object in the tree"""
    # Tree structure
    parent: Optional['S3Node'] = None
    children: List['S3Node'] = field(default_factory=list)
    is_loaded: bool = False

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

    def run(self):
        if self._is_running:
            return
            
        self._is_running = True
        try:
            if self._bucket is None:
                # Load buckets in thread
                items = self._s3_service.list_buckets()
                nodes = [self._create_node(item, self._parent_node) for item in items]
            else:
                # Load objects in thread
                items = self._list_objects()  # This runs in the worker thread
                nodes = [self._create_node(item, self._parent_node) for item in items]

            if self._is_running:
                self.finished.emit(nodes)
                
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._is_running = False


class ChildrenCheckerThread(QThread):
    finished = pyqtSignal(bool)
    
    def __init__(self, s3_service, node):
        super().__init__()
        self._s3_service = s3_service
        self._node = node
        self._is_running = False
        
    def run(self):
        self._is_running = True
        try:
            # For buckets, check first object
            if self._node.type == ObjectType.BUCKET:
                objects = self._s3_service.list_objects(self._node.name, prefix="", max_keys=1)
            # For folders, check first object in folder
            else:
                objects = self._s3_service.list_objects(self._node.bucket, prefix=f"{self._node.key}/", max_keys=1)
            
            # If we got any objects, this node has children
            has_children = next(objects, None) is not None
            if self._is_running:
                self.finished.emit(has_children)
        except Exception:
            if self._is_running:
                self.finished.emit(False)
        finally:
            self._is_running = False
            
    def stop(self):
        self._is_running = False


class S3FileTreeModel(QAbstractItemModel):
    error_occurred = pyqtSignal(str)
    loading_started = pyqtSignal()  # Add loading_started signal
    loading_finished = pyqtSignal()

    # Column indices
    NAME, TYPE, SIZE, MODIFIED = range(4)

    def __init__(self, parent=None, s3_service=None):
        super().__init__(parent)
        self._s3_service = s3_service
        
        self.root = S3Node(
            name="",
            type=ObjectType.FOLDER,
            parent=None
        )
        
        self._setup_icons()
        self._current_worker = None
        self._children_checkers = {}  # Store checkers by node
        self._has_children_cache = {}  # Cache results

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

    def _on_nodes_loaded(self, nodes: List[S3Node], parent_node: S3Node, parent_index: QModelIndex) -> None:
        """Handle loaded nodes"""
        try:
            self.beginInsertRows(parent_index, 0, len(nodes) - 1)
            
            # Clear existing children if any
            parent_node.children.clear()
            
            # Add new nodes, avoiding duplicates
            for node in nodes:
                # Check if node already exists
                exists = False
                for existing in parent_node.children:
                    if existing.name == node.name and existing.type == node.type:
                        exists = True
                        break
                
                if not exists:
                    node.parent = parent_node
                    parent_node.children.append(node)
            
            parent_node.is_loaded = True
            self.endInsertRows()
            self.loading_finished.emit()
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to process loaded nodes: {str(e)}")
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
        return node.can_fetch_more()

    def fetchMore(self, parent: QModelIndex) -> None:
        """Fetch child items for the given index"""
        if not parent.isValid():
            return

        node = self.get_node(parent)
        if not node.can_fetch_more():
            return

        try:
            self.loading_started.emit()  # Emit before starting to load
            self._fetch_children(node, parent)
        except Exception as e:
            self.error_occurred.emit(f"Failed to fetch contents: {str(e)}")
            self.loading_finished.emit()  # Emit on error

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
        """Clean up all children checker threads"""
        for checker in self._children_checkers.values():
            try:
                checker.stop()
                checker.finished.disconnect()
                checker.quit()
                checker.wait(1000)  # Wait up to 1 second
                checker.deleteLater()
            except:
                pass
        self._children_checkers.clear()

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        """Check if the index can have children"""
        if not parent.isValid():
            return True  # Root can have children
        
        node = self.get_node(parent)
        
        # If we already have children, return True
        if len(node.children) > 0:
            return True
        
        # Check cache first
        node_id = id(node)
        if node_id in self._has_children_cache:
            return self._has_children_cache[node_id]
        
        # If we haven't loaded yet and it's a bucket or folder
        if not node.is_loaded and node.type in (ObjectType.BUCKET, ObjectType.FOLDER):
            # Clean up any existing checker for this node
            if node_id in self._children_checkers:
                old_checker = self._children_checkers[node_id]
                old_checker.stop()
                old_checker.finished.disconnect()
                old_checker.quit()
                old_checker.wait(1000)
                old_checker.deleteLater()
            
            # Start background check if not already running
            checker = ChildrenCheckerThread(self._s3_service, node)
            checker.finished.connect(lambda has_children: self._on_children_checked(node_id, has_children))
            self._children_checkers[node_id] = checker
            checker.start()
            
            # Return True while checking to show expand arrow
            return True
            
        return False

    def _on_children_checked(self, node_id, has_children):
        """Handle completion of children check"""
        # Cache the result
        self._has_children_cache[node_id] = has_children
        
        # Clean up the checker
        if node_id in self._children_checkers:
            checker = self._children_checkers[node_id]
            checker.stop()
            checker.finished.disconnect()
            checker.quit()
            checker.wait(1000)
            checker.deleteLater()
            del self._children_checkers[node_id]
        
        # Emit dataChanged to update the view
        self.layoutChanged.emit()

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
            node_id = id(node)
            
            # Clean up any existing checker
            if node_id in self._children_checkers:
                checker = self._children_checkers[node_id]
                checker.stop()
                checker.finished.disconnect()
                checker.quit()
                checker.wait(1000)
                checker.deleteLater()
                del self._children_checkers[node_id]
                
            if node_id in self._has_children_cache:
                del self._has_children_cache[node_id]

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
        self._cleanup_checkers()