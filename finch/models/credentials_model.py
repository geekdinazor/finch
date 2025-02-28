import keyring
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex
from slugify import slugify

from finch.utils.config import get_credentials, write_credentials, get_credentials_names
from finch.views.error import show_error_dialog


class CredentialsModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.credentials_data = get_credentials()
        self._column_map = {
            "name": "Credential Name",
            "endpoint": "Service Endpoint",
            "use_ssl": "Use SSL",
            "verify_ssl": "Verify SSL",
            "access_key": "Access Key",
            "secret_key": "Secret Key",
            "region": "Region"
        }
        self._data = []


        for cdata in self.credentials_data:
            d = {}
            for field in cdata:
                d[self._column_map[field]] = cdata[field]
                # Hide the secret key if not modified
                if field == "access_key":
                    d["Secret Key"] = "xxx"

            for k in ["Use SSL", "Verify SSL"]:
                if not k in d:
                    d[k] = True

            self._data.append(d)
        self._deleted_credentials = []
        # --- End of merged TempCredentialsData initialization ---

    # --- Data manipulation methods (from TempCredentialsData) ---
    def get_data(self):
        return self._data

    def get_value(self, row: int, col: int):
        if self._data:
            try:
                return self._data[row][self.get_columns()[col]]
            except KeyError:
                pass
        return ""

    def set_value(self, row: int, col: int, data: str):
        self._data[row][self.get_columns()[col]] = data

    def get_columns(self):
        return list(self._column_map.values())

    def insert_row(self):
        new_row = {
            "Credential Name": "",
            "Service Endpoint": "https://s3.amazonaws.com",
            "Use SSL": True,
            "Verify SSL": True,
            "Access Key": "",
            "Secret Key": "",
            "Region": "us-east-1",
        }
        # Inform views about the new row.
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        self._data.append(new_row)
        self.endInsertRows()

    def delete_row(self, index):
        if 0 <= index < len(self._data):
            self.beginRemoveRows(QModelIndex(), index, index)
            d = self._data.pop(index)
            self.endRemoveRows()
            self._deleted_credentials.append(d)

    def persist_data(self):
        credentials_data = []
        # Invert the column map for saving data.
        inverted_map = {v: k for k, v in self._column_map.items()}

        for data in self._data:
            d = {}
            for field in data:
                if field == "Secret Key":
                    # Save only if the secret key has been modified.
                    if data["Secret Key"] != 'xxx':
                        keyring.set_password(
                            f'{slugify(data["Credential Name"])}@finch',
                            data["Access Key"],
                            data["Secret Key"]
                        )
                else:
                    d[inverted_map[field]] = data[field]
            credentials_data.append(d)

        write_credentials(credentials_data)

        # Process deleted credentials
        for credential in self._deleted_credentials:
            cname = credential["Credential Name"]
            if cname.strip() and cname.strip() in get_credentials_names():
                try:
                    keyring.delete_password(
                        f'{slugify(cname.strip())}@finch',
                        credential["Access Key"]
                    )
                except keyring.errors.PasswordDeleteError:
                    show_error_dialog(f'Keyring deletion error', show_traceback=True)
        self._deleted_credentials = []
    # --- End of data manipulation methods ---

    # --- QAbstractTableModel methods ---
    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.get_columns())

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
            
        column_name = self.get_columns()[index.column()]
        
        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self.get_value(index.row(), index.column())
            if column_name in ["Use SSL", "Verify SSL"]:
                return bool(value) if value is not None else False
            return value
            
        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.get_columns()[section]
        return None

    def flags(self, index):
        column_name = self.get_columns()[index.column()]
        
        if column_name in ["Use SSL", "Verify SSL"]:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
            
        if index.column() != 0:
            return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
        else:
            if index.data():
                return Qt.ItemIsEnabled | Qt.ItemIsSelectable
            else:
                return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        if role == Qt.EditRole:
            if index.column() == 0 and value and self.hasDuplicate(value):
                show_error_dialog("Credential name already exists")
                return False
            else:
                self.set_value(index.row(), index.column(), value)
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
                
        return False

    def hasDuplicate(self, value):
        value_slug = slugify(value)
        for i in range(self.rowCount()):
            current_value = self.index(i, 0).data()
            if current_value and slugify(current_value) == value_slug:
                return True
        return False

    def validateData(self):
        # Make sure that no field is empty (after stripping white spaces).
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                cell_data = self.index(i, j).data()
                cell_data = cell_data.strip() if type(cell_data) == str else cell_data
                if cell_data is None or cell_data == '':
                    raise ValueError(f"Field {self.get_columns()[j]} cannot be empty")