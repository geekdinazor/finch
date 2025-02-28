from PyQt5.QtCore import pyqtSignal, Qt, QRect, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QStyledItemDelegate, QApplication, QStyle, QWidget, QTableView, 
    QAction, QBoxLayout, QToolBar, QAbstractItemView, QHeaderView, 
    QItemDelegate, QVBoxLayout, QCheckBox, QStyleOptionButton
)

from finch.models.credentials_model import CredentialsModel, show_error_dialog
from finch.utils.ui import center_window

class TableViewEditorDelegate(QItemDelegate):

    def setEditorData(self, editor, index):
        editor.setAutoFillBackground(True)
        editor.setText(index.data())

class PasswordDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)

        style = option.widget.style() or QApplication.style()
        hint = style.styleHint(QStyle.SH_LineEdit_PasswordCharacter)
        if len(index.data()) > 0:
            option.text = chr(hint) * 6

class CheckBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        return None  # Disable editor creation - we'll handle clicks directly

    def editorEvent(self, event, model, option, index):
        if event.type() == event.MouseButtonRelease:
            current_value = index.data(Qt.EditRole)
            model.setData(index, not bool(current_value), Qt.EditRole)
            return True
        return False

    def paint(self, painter, option, index):
        painter.save()
        
        # Get the style from the parent widget
        style = option.widget.style() or QApplication.style()
        
        # Draw the item background
        style.drawControl(QStyle.CE_ItemViewItem, option, painter, option.widget)
        
        # Setup the style option for the checkbox
        check_option = QStyleOptionButton()
        check_option.state = QStyle.State_Enabled
        if bool(index.data(Qt.EditRole)):
            check_option.state |= QStyle.State_On
        else:
            check_option.state |= QStyle.State_Off
            
        # Center the checkbox
        check_rect = style.subElementRect(QStyle.SE_CheckBoxIndicator, check_option, option.widget)
        check_point = QPoint(
            option.rect.x() + option.rect.width() // 2 - check_rect.width() // 2,
            option.rect.y() + option.rect.height() // 2 - check_rect.height() // 2
        )
        check_option.rect = QRect(check_point, check_rect.size())
        
        # Draw the checkbox using the native style
        style.drawControl(QStyle.CE_CheckBox, check_option, painter, option.widget)
        
        painter.restore()

class ManageCredentialsWindow(QWidget):
    window_closed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Manage Credentials")
        self.resize(800, 500)
        center_window(self)
        self.model = CredentialsModel()

        self.tool_layout = QBoxLayout(QBoxLayout.TopToBottom, self)
        self.tool_layout.setContentsMargins(0, 0, 0, 0)
        self.credential_toolbar = QToolBar("Credential")
        self.credential_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        add_row_action = QAction(self)
        add_row_action.setText("&Create Credential")
        add_row_action.setIcon(QIcon(':/icons/new-credential.svg'))
        add_row_action.triggered.connect(self.add_row)

        self.delete_row_action = QAction(self)
        self.delete_row_action.setText("&Delete Credential")
        self.delete_row_action.setIcon(QIcon(':/icons/trash.svg'))
        self.delete_row_action.triggered.connect(self.delete_row)

        self.credential_toolbar.addAction(add_row_action)

        self.table_data = QTableView()
        self.table_data.setModel(self.model)
        self.selection = self.table_data.selectionModel()
        self.selection.selectionChanged.connect(self.handleSelectionChanged)
        self.table_data.model().layoutChanged.connect(self.handleTableLayoutChanged)
        self.table_data.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_data.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table_data.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_data.setStyleSheet("""
        QTableView::item{
            padding: 5px 5px 5px 5px;
        }
        """)

        table_view_editor_delegate = TableViewEditorDelegate(self.table_data)
        self.table_data.setItemDelegate(table_view_editor_delegate)

        self.password_delegate = PasswordDelegate()
        self.table_data.setItemDelegateForColumn(5, self.password_delegate)

        # Set delegates for SSL columns
        ssl_delegate = CheckBoxDelegate(self.table_data)
        verify_ssl_column = self.model.get_columns().index("Verify SSL")
        self.table_data.setItemDelegateForColumn(2, ssl_delegate)
        self.table_data.setItemDelegateForColumn(3, ssl_delegate)

        layout = QVBoxLayout()
        self.tool_layout.addWidget(self.table_data)
        self.tool_layout.setMenuBar(self.credential_toolbar)
        self.tool_layout.addLayout(layout)

    def add_row(self):
        self.model.insert_row()
        model = self.table_data.model()
        model.insertRow(model.rowCount())
        model.itemData(model.index(model.rowCount() - 1, 0))
        self.table_data.model().layoutChanged.emit()
        self.table_data.selectRow(model.rowCount() - 1)
        self.credential_toolbar.addAction(self.delete_row_action)

    def delete_row(self):
        indexes = self.table_data.selectedIndexes()
        row = indexes[0].row()
        self.model.delete_row(row)
        self.table_data.model().layoutChanged.emit()
        self.credential_toolbar.removeAction(self.delete_row_action)

    def save_credentials(self):
        if self.table_data.model().rowCount() > 0:
            self.table_data.model().validateData()
        self.model.persist_data()
        self.table_data.model().layoutChanged.emit()

    def handleSelectionChanged(self, selected, deselected):
        self.credential_toolbar.addAction(self.delete_row_action)

    def handleTableLayoutChanged(self):
        if self.table_data.model().rowCount() == 0:
            self.credential_toolbar.removeAction(self.delete_row_action)

    def closeEvent(self, event):
        try:
            self.save_credentials()
            self.window_closed.emit()
            event.accept()
        except ValueError as e:
            show_error_dialog(f"Validation error: {e}")
            event.ignore()
        except Exception as e:
            show_error_dialog(f"Unknown error: {e}")
            event.ignore()