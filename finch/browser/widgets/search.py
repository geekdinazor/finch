import asyncio
import re

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QStyle, QLabel, QFrame,
)

from finch.s3 import s3_service
from finch.config import ObjectType
from finch.utils.text import format_datetime, format_size
from finch.utils.ui import resource_path


class SearchScope:
    def __init__(self, bucket_name: str, prefix: str = ''):
        self.bucket_name = bucket_name
        self.prefix = prefix  # folder key with trailing slash, or ''

    def label(self) -> str:
        if self.prefix:
            parts = self.prefix.rstrip('/').split('/')
            return f"{self.bucket_name} > {' > '.join(parts)}"
        return self.bucket_name


class ScopeChip(QFrame):
    def __init__(self, scope: SearchScope, on_remove):
        super().__init__()
        self.scope = scope
        self.setObjectName("scope-chip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 6, 3)
        layout.setSpacing(6)
        layout.addWidget(QLabel(scope.label()))
        btn = QPushButton("✕")
        btn.setFlat(True)
        btn.setFixedSize(16, 16)
        btn.clicked.connect(lambda: on_remove(self))
        layout.addWidget(btn)


class SearchWidget(QWidget):
    def __init__(self, main_widget: QWidget, scopes: list = None):
        super().__init__()
        self.main_widget = main_widget
        self._scopes: list[SearchScope] = list(scopes or [])
        self._chip_widgets: list[ScopeChip] = []
        self._results_tree: QTreeWidget | None = None
        self._icon_type = self._init_icons()
        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()

    def close(self):
        super().close()
        self.main_widget.file_toolbar.enable_search()
        self.main_widget.layout.removeWidget(self)
        self._hide_results()

    # ── Results tree ───────────────────────────────────────────────────────

    def _hide_results(self):
        if self._results_tree is not None:
            self.main_widget.layout.removeWidget(self._results_tree)
            self._results_tree.setParent(None)
            self._results_tree = None
            self.main_widget.tree_widget.show()

    def _ensure_results_visible(self):
        if self._results_tree is None:
            self._results_tree = self._make_results_tree()
            self.main_widget.tree_widget.hide()
            # Insert above the search widget so results sit between tree area and search bar
            idx = self.main_widget.layout.indexOf(self)
            self.main_widget.layout.insertWidget(idx, self._results_tree)

    def _make_results_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setColumnCount(4)
        tree.setHeaderLabels(["Name", "Type", "Size", "Date"])
        tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        tree.setSortingEnabled(True)
        header = tree.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        return tree

    def _init_icons(self):
        style = self.style()
        return {
            ObjectType.FILE:   style.standardIcon(QStyle.SP_FileIcon),
            ObjectType.FOLDER: style.standardIcon(QStyle.SP_DirIcon),
            ObjectType.BUCKET: style.standardIcon(QStyle.SP_DirIcon),
        }

    # ── UI ─────────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(4)

        # Chips row (only shown when there are scopes)
        self._chips_row = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(4)
        self._chips_layout.addStretch()
        for scope in self._scopes:
            self._insert_chip(scope)
        self._chips_row.setVisible(bool(self._scopes))
        root.addWidget(self._chips_row)

        # Search row
        row = QHBoxLayout()
        row.setSpacing(4)

        self.search_input = QLineEdit(placeholderText="Search")
        self.search_input.returnPressed.connect(self._on_search)
        row.addWidget(self.search_input)

        self.case_btn = QPushButton("Cc")
        self.case_btn.setCheckable(True)
        self.case_btn.setFixedWidth(36)
        self.case_btn.setToolTip("Case sensitive")
        row.addWidget(self.case_btn)

        self.regex_btn = QPushButton(".*")
        self.regex_btn.setCheckable(True)
        self.regex_btn.setFixedWidth(36)
        self.regex_btn.setToolTip("Regular expression")
        row.addWidget(self.regex_btn)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._on_search)
        row.addWidget(self.search_button)

        close_btn = QPushButton()
        close_btn.setIcon(QIcon(resource_path('img/close.svg')))
        close_btn.setFlat(True)
        close_btn.setObjectName("btn-flat")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)

        root.addLayout(row)

    # ── Chips ──────────────────────────────────────────────────────────────

    def _insert_chip(self, scope: SearchScope):
        chip = ScopeChip(scope, self._remove_chip)
        self._chip_widgets.append(chip)
        self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)

    def _remove_chip(self, chip: ScopeChip):
        self._chip_widgets.remove(chip)
        self._chips_layout.removeWidget(chip)
        chip.setParent(None)
        self._scopes.remove(chip.scope)
        self._chips_row.setVisible(bool(self._scopes))

    # ── Search ─────────────────────────────────────────────────────────────

    def _on_search(self):
        term = self.search_input.text()
        if not term:
            return
        asyncio.ensure_future(self._search_async(term))

    async def _search_async(self, term: str):
        self._ensure_results_visible()
        self._results_tree.clear()
        case_sensitive = self.case_btn.isChecked()
        use_regex = self.regex_btn.isChecked()

        self.main_widget.spinner.start()
        try:
            if self._scopes:
                results = await asyncio.gather(*[
                    asyncio.to_thread(self._search_scope, s, term, case_sensitive, use_regex)
                    for s in self._scopes
                ])
                bucket_items: dict[str, list] = {}
                for scope, items in zip(self._scopes, results):
                    bucket_items.setdefault(scope.bucket_name, []).extend(items)
            else:
                buckets = await asyncio.to_thread(s3_service.list_buckets)
                results = await asyncio.gather(*[
                    asyncio.to_thread(
                        self._search_scope, SearchScope(b.name),
                        term, case_sensitive, use_regex,
                    )
                    for b in buckets
                ])
                bucket_items = {b.name: items for b, items in zip(buckets, results)}
        finally:
            self.main_widget.spinner.stop()

        for bucket_name, items in bucket_items.items():
            if not items:
                continue
            bucket_item = self._make_item(bucket_name, ObjectType.BUCKET)
            self._results_tree.addTopLevelItem(bucket_item)
            self._populate_tree(bucket_item, self._build_tree(items))

        for i in range(self._results_tree.topLevelItemCount()):
            self._expand_matching(self._results_tree.topLevelItem(i), term)

    def _search_scope(self, scope: SearchScope, term: str,
                      case_sensitive: bool, use_regex: bool) -> list:
        items = []
        paginator = s3_service.client.get_paginator('list_objects_v2')
        kwargs = {'Bucket': scope.bucket_name}
        if scope.prefix:
            kwargs['Prefix'] = scope.prefix
        for page in paginator.paginate(**kwargs):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if self._matches(key, term, case_sensitive, use_regex):
                    items.append((key, obj['Size'], obj['LastModified']))
        return items

    def _matches(self, key: str, term: str, case_sensitive: bool, use_regex: bool) -> bool:
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                return bool(re.search(term, key, flags))
            except re.error:
                return False
        if case_sensitive:
            return term in key
        return term.lower() in key.lower()

    # ── Tree building ──────────────────────────────────────────────────────

    def _build_tree(self, objects: list) -> dict:
        tree: dict = {}
        for path, size, date in objects:
            current = tree
            parts = path.split('/')
            if path.endswith('/'):
                for folder in parts[:-1]:
                    current = current.setdefault(folder, {})
            else:
                *folders, filename = parts
                for folder in folders:
                    current = current.setdefault(folder, {})
                current[filename] = {"_info": (size, date)}
        return tree

    def _populate_tree(self, parent: QTreeWidgetItem, tree_dict: dict):
        for key, value in sorted(tree_dict.items()):
            if key != "_info" and "_info" not in value:
                item = self._make_item(key, ObjectType.FOLDER)
                parent.addChild(item)
                self._populate_tree(item, value)
        for key, value in sorted(tree_dict.items()):
            if key != "_info" and "_info" in value:
                size, date = value["_info"]
                item = self._make_item(key, ObjectType.FILE, size, date)
                parent.addChild(item)

    def _expand_matching(self, item: QTreeWidgetItem, term: str):
        if item.childCount():
            item.setExpanded(True)
        if term.lower() in item.text(0).lower():
            item.setSelected(True)
        for i in range(item.childCount()):
            self._expand_matching(item.child(i), term)

    def _make_item(self, name: str, obj_type: ObjectType,
                   size: int = 0, date=None) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setText(0, name)
        item.setIcon(0, self._icon_type[obj_type])
        item.setText(1, obj_type)
        item.setText(2, format_size(size))
        item.setText(3, format_datetime(date))
        return item