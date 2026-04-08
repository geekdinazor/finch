from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QBoxLayout, QTableView, QToolBar,
    QAbstractItemView, QHeaderView,
)

from finch.settings.credentials.manager import CredentialsDraft
from finch.settings.credentials.model import CredentialsModel, TextEditorDelegate, PasswordDelegate
from finch.utils.ui import resource_path


class CredentialsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._draft = CredentialsDraft()
        self._build_ui()

    def _build_ui(self):
        layout = QBoxLayout(QBoxLayout.TopToBottom, self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QToolBar("Credential")
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        add_action = QAction(self)
        add_action.setText("&Add Credential")
        add_action.setIcon(QIcon(resource_path('img/new-credential.svg')))
        add_action.triggered.connect(self._add_row)
        toolbar.addAction(add_action)

        self._delete_action = QAction(self)
        self._delete_action.setText("&Delete Credential")
        self._delete_action.setIcon(QIcon(resource_path('img/trash.svg')))
        self._delete_action.triggered.connect(self._delete_row)

        self.table = QTableView()
        self.table.setModel(CredentialsModel(self._draft))
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.model().layoutChanged.connect(self._on_layout_changed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setItemDelegate(TextEditorDelegate(self.table))
        self.table.setItemDelegateForColumn(3, PasswordDelegate())

        layout.setMenuBar(toolbar)
        layout.addWidget(self.table)
        self._toolbar = toolbar

    def _add_row(self):
        self._draft.insert_row()
        model = self.table.model()
        model.insertRow(model.rowCount())
        model.layoutChanged.emit()
        self.table.selectRow(model.rowCount() - 1)
        self._toolbar.addAction(self._delete_action)

    def _delete_row(self):
        indexes = self.table.selectedIndexes()
        if indexes:
            self._draft.delete_row(indexes[0].row())
            self.table.model().layoutChanged.emit()
            self._toolbar.removeAction(self._delete_action)

    def _on_selection_changed(self, selected, deselected):
        self._toolbar.addAction(self._delete_action)

    def _on_layout_changed(self):
        if self.table.model().rowCount() == 0:
            self._toolbar.removeAction(self._delete_action)

    def save(self):
        """Validate and persist. Raises ValueError on invalid data."""
        if self.table.model().rowCount() > 0:
            self.table.model().validate()
        self._draft.persist()
        self.table.model().layoutChanged.emit()