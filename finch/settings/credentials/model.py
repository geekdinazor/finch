from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QApplication, QItemDelegate, QStyle, QStyledItemDelegate
from slugify import slugify

from finch.settings.credentials.manager import COLUMNS, CredentialsDraft
from finch.utils.error import show_error_dialog


class CredentialsModel(QAbstractTableModel):
    def __init__(self, draft: CredentialsDraft, parent=None):
        super().__init__(parent)
        self._draft = draft

    def rowCount(self, parent=None) -> int:
        return self._draft.row_count()

    def columnCount(self, parent=None) -> int:
        return len(COLUMNS)

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        # Credential name is locked once set; all other fields are always editable.
        if index.column() != 0 or not index.data():
            return base | Qt.ItemIsEditable
        return base

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            return self._draft.get_value(index.row(), index.column())
        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section][1]
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if value and index.column() == 0 and self._has_duplicate(value):
            show_error_dialog("A credential with this name already exists")
        elif value:
            self._draft.set_value(index.row(), index.column(), value)
            self.dataChanged.emit(index, index, (Qt.DisplayRole,))
        return True

    def validate(self) -> None:
        """Raise ValueError if any required field is blank."""
        for i in range(self.rowCount()):
            for col, (key, display) in enumerate(COLUMNS):
                if key == "secret_key":
                    continue  # placeholder is acceptable
                if not (self._draft.get_value(i, col) or "").strip():
                    raise ValueError(f"'{display}' cannot be empty (row {i + 1})")

    def _has_duplicate(self, value: str) -> bool:
        slug = slugify(value)
        return any(
            slugify(self.index(i, 0).data() or "") == slug
            for i in range(self.rowCount())
        )


class TextEditorDelegate(QItemDelegate):
    """Standard text editor delegate with auto-fill background."""

    def setEditorData(self, editor, index):
        editor.setAutoFillBackground(True)
        editor.setText(index.data())


class PasswordDelegate(QStyledItemDelegate):
    """Renders cell content as password bullets."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        style = option.widget.style() or QApplication.style()
        hint = style.styleHint(QStyle.SH_LineEdit_PasswordCharacter)
        if index.data():
            option.text = chr(hint) * 6