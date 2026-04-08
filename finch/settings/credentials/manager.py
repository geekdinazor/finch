import json
import os
from typing import List

import keyring
from slugify import slugify

from finch.config import CONFIG_PATH
from finch.utils.error import show_error_dialog


# Column definitions shared with the Qt model: (internal_key, display_name).
# Order determines column order in the table view.
COLUMNS = [
    ("name",       "Credential Name"),
    ("endpoint",   "Service Endpoint"),
    ("access_key", "Access Key"),
    ("secret_key", "Secret Key"),
    ("region",     "Region"),
]

_SECRET_PLACEHOLDER = "xxx"


class CredentialsManager:
    """Reads and writes credentials.json; secrets are stored in the system keyring."""

    def __init__(self):
        path = os.path.join(CONFIG_PATH, "credentials.json")
        with open(path, "r") as f:
            try:
                self.credentials: List[dict] = json.loads(f.read())
            except json.JSONDecodeError:
                self.credentials = []

    def get_credential(self, name: str) -> dict:
        matches = [c for c in self.credentials if c["name"] == name]
        return matches[0] if matches else {}

    def get_credentials(self) -> List[dict]:
        return self.credentials

    def save_credentials(self, credentials: List[dict]) -> None:
        with open(os.path.join(CONFIG_PATH, "credentials.json"), "w") as f:
            json.dump(credentials, f)

    def list_credentials_names(self) -> List[str]:
        return sorted(c["name"] for c in self.credentials)


class CredentialsDraft:
    """In-memory staging buffer for editing credentials before persisting.

    Rows are stored with internal keys (matching credentials.json).
    The secret_key field is masked with a placeholder for existing credentials.
    """

    def __init__(self):
        self._rows: List[dict] = []
        self._deleted: List[dict] = []

        for cred in CredentialsManager().get_credentials():
            self._rows.append({**cred, "secret_key": _SECRET_PLACEHOLDER})

    def row_count(self) -> int:
        return len(self._rows)

    def get_value(self, row: int, col: int) -> str:
        return self._rows[row].get(COLUMNS[col][0], "")

    def set_value(self, row: int, col: int, value: str) -> None:
        self._rows[row][COLUMNS[col][0]] = value

    def insert_row(self) -> None:
        self._rows.append({
            "name":       "",
            "endpoint":   "https://s3.amazonaws.com",
            "access_key": "",
            "secret_key": "",
            "region":     "us-east-1",
        })

    def delete_row(self, index: int) -> None:
        self._deleted.append(self._rows.pop(index))

    def persist(self) -> None:
        """Write secrets to keyring and save credential metadata to disk."""
        to_save = []
        for row in self._rows:
            if row["secret_key"] != _SECRET_PLACEHOLDER:
                keyring.set_password(
                    f'{slugify(row["name"])}@finch',
                    row["access_key"],
                    row["secret_key"],
                )
            to_save.append({k: v for k, v in row.items() if k != "secret_key"})

        CredentialsManager().save_credentials(to_save)

        for cred in self._deleted:
            service = f'{slugify(cred["name"])}@finch'
            if keyring.get_password(service, cred["access_key"]) is not None:
                try:
                    keyring.delete_password(service, cred["access_key"])
                except keyring.errors.PasswordDeleteError as e:
                    show_error_dialog(f"Keyring deletion error: {e}", show_traceback=True)
        self._deleted.clear()