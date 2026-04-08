import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Signal, Qt, QModelIndex, QAbstractItemModel
from PySide6.QtWidgets import QApplication, QStyle

from finch.s3 import s3_service, S3Object
from finch.config import ObjectType, app_settings
from finch.utils.text import format_size, format_datetime


@dataclass
class S3Node:
    s3_object: Optional[S3Object]
    parent: Optional['S3Node'] = field(default=None, repr=False)
    children: List['S3Node'] = field(default_factory=list)
    is_loaded: bool = False
    is_loading: bool = False

    @property
    def row(self) -> int:
        if self.parent:
            return self.parent.children.index(self)
        return 0


class S3FileTreeModel(QAbstractItemModel):
    loading_started = Signal()
    loading_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = S3Node(s3_object=None)
        self._active_loads: int = 0
        style = QApplication.style()
        self._icons = {
            ObjectType.FILE: style.standardIcon(QStyle.SP_FileIcon),
            ObjectType.FOLDER: style.standardIcon(QStyle.SP_DirIcon),
            ObjectType.BUCKET: style.standardIcon(QStyle.SP_DirIcon),
        }

    # ── Core QAbstractItemModel interface ──────────────────────────────────

    def index(self, row: int, col: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, col, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        if row < len(parent_node.children):
            return self.createIndex(row, col, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: S3Node = index.internalPointer()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row, 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        return len(parent_node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 4

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        node: S3Node = index.internalPointer()
        obj = node.s3_object
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return obj.name
            if col == 1:
                return obj.type
            if col == 2:
                return format_size(obj.size)
            if col == 3:
                return format_datetime(obj.last_modified)
        elif role == Qt.DecorationRole and col == 0:
            return self._icons.get(obj.type)
        elif role == Qt.UserRole:
            return node
        return None

    def headerData(self, section: int, orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["Name", "Type", "Size", "Date"][section]
        return None

    # ── Lazy loading ───────────────────────────────────────────────────────

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return bool(self._root.children)
        node: S3Node = parent.internalPointer()
        obj = node.s3_object
        if obj.type not in (ObjectType.BUCKET, ObjectType.FOLDER):
            return False
        if node.is_loaded:
            return bool(node.children)
        return True

    def canFetchMore(self, parent: QModelIndex) -> bool:
        if not parent.isValid():
            return False
        node: S3Node = parent.internalPointer()
        return (
            node.s3_object.type in (ObjectType.BUCKET, ObjectType.FOLDER)
            and not node.is_loaded
            and not node.is_loading
        )

    def fetchMore(self, parent: QModelIndex):
        if not parent.isValid():
            return
        node: S3Node = parent.internalPointer()
        if node.is_loading or node.is_loaded:
            return
        node.is_loading = True
        self._inc_load()
        asyncio.ensure_future(self._fetch_async(node))

    async def _fetch_async(self, node: S3Node):
        try:
            obj = node.s3_object
            if obj.type == ObjectType.BUCKET:
                objects = await asyncio.to_thread(s3_service.list_objects, obj.name, '')
            else:
                objects = await asyncio.to_thread(s3_service.list_objects, obj.bucket_name, obj.key)
        except Exception:
            objects = []
        self._on_objects_loaded(node, objects)

    def _on_objects_loaded(self, node: S3Node, objects: list):
        parent_index = self._node_to_index(node)
        if objects:
            self.beginInsertRows(parent_index, 0, len(objects) - 1)
            for obj in objects:
                node.children.append(S3Node(s3_object=obj, parent=node))
            self.endInsertRows()
            if app_settings.check_folder_contents:
                for child in node.children:
                    if child.s3_object.type == ObjectType.FOLDER:
                        asyncio.ensure_future(self._empty_check_async(child))
        node.is_loaded = True
        node.is_loading = False
        self._dec_load()

    # ── Empty-folder check ─────────────────────────────────────────────────

    async def _empty_check_async(self, node: S3Node):
        self._inc_load()
        try:
            obj = node.s3_object
            objects = await asyncio.to_thread(s3_service.list_objects, obj.bucket_name, obj.key)
            is_empty = len(objects) == 0
        except Exception:
            is_empty = False
        self._on_empty_check_done(node, is_empty)

    def _on_empty_check_done(self, node: S3Node, is_empty: bool):
        if is_empty:
            node.is_loaded = True
            idx = self._node_to_index(node)
            self.dataChanged.emit(idx, idx)
        self._dec_load()

    # ── Bucket loading ─────────────────────────────────────────────────────

    def load_buckets(self):
        """Clear tree and reload all buckets from S3."""
        self.beginResetModel()
        self._root.children.clear()
        self.endResetModel()
        self._inc_load()
        asyncio.ensure_future(self._load_buckets_async())

    async def _load_buckets_async(self):
        try:
            buckets = await asyncio.to_thread(s3_service.list_buckets)
        except Exception:
            buckets = []
        self._on_buckets_loaded(buckets)

    def _on_buckets_loaded(self, buckets: list):
        if buckets:
            self.beginInsertRows(QModelIndex(), 0, len(buckets) - 1)
            for bucket in buckets:
                self._root.children.append(S3Node(s3_object=bucket, parent=self._root))
            self.endInsertRows()
        self._dec_load()

    # ── Loading state ──────────────────────────────────────────────────────

    def _inc_load(self):
        if self._active_loads == 0:
            self.loading_started.emit()
        self._active_loads += 1

    def _dec_load(self):
        self._active_loads = max(0, self._active_loads - 1)
        if self._active_loads == 0:
            self.loading_finished.emit()

    # ── Direct tree mutations ──────────────────────────────────────────────

    def insert_child(self, parent_node: S3Node, s3_object: S3Object) -> S3Node:
        """Append a new child to parent_node without reloading the whole tree."""
        parent_index = self._node_to_index(parent_node)
        row = len(parent_node.children)
        self.beginInsertRows(parent_index, row, row)
        new_node = S3Node(s3_object=s3_object, parent=parent_node)
        parent_node.children.append(new_node)
        self.endInsertRows()
        return new_node

    def remove_node(self, node: S3Node) -> None:
        """Remove node from its parent without reloading the whole tree."""
        parent_node = node.parent
        if parent_node is None:
            return
        row = node.row
        parent_index = self._node_to_index(parent_node)
        self.beginRemoveRows(parent_index, row, row)
        parent_node.children.remove(node)
        self.endRemoveRows()

    def find_node(self, bucket_name: str, prefix: str = '') -> Optional['S3Node']:
        """Return the loaded node at bucket/prefix, or None if not in the tree."""
        bucket_node = next(
            (c for c in self._root.children if c.s3_object.name == bucket_name), None
        )
        if bucket_node is None:
            return None
        if not prefix:
            return bucket_node
        return self._find_in_node(bucket_node, prefix)

    def _find_in_node(self, node: S3Node, key: str) -> Optional['S3Node']:
        for child in node.children:
            if child.s3_object.key == key:
                return child
            if key.startswith(child.s3_object.key) and child.is_loaded:
                result = self._find_in_node(child, key)
                if result:
                    return result
        return None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _node_to_index(self, node: S3Node, col: int = 0) -> QModelIndex:
        if node is self._root or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.row, col, node)
