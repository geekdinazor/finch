import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from finch.settings.credentials.manager import (
    COLUMNS,
    CredentialsDraft,
    CredentialsManager,
)

SAMPLE_CREDS = [
    {"name": "prod", "endpoint": "https://s3.amazonaws.com", "access_key": "AKIA1", "region": "us-east-1"},
    {"name": "dev",  "endpoint": "https://minio.local",      "access_key": "AKIA2", "region": "eu-west-1"},
]


def make_manager(creds=None):
    data = creds if creds is not None else SAMPLE_CREDS
    m = mock_open(read_data=json.dumps(data))
    with patch("builtins.open", m):
        return CredentialsManager()


class TestCredentialsManager:
    def test_get_credentials(self):
        mgr = make_manager()
        assert mgr.get_credentials() == SAMPLE_CREDS

    def test_list_credentials_names_sorted(self):
        mgr = make_manager()
        assert mgr.list_credentials_names() == ["dev", "prod"]

    def test_get_credential_found(self):
        mgr = make_manager()
        assert mgr.get_credential("prod") == SAMPLE_CREDS[0]

    def test_get_credential_not_found(self):
        mgr = make_manager()
        assert mgr.get_credential("missing") == {}

    def test_get_credentials_bad_json(self):
        with patch("builtins.open", mock_open(read_data="!!invalid!!")):
            mgr = CredentialsManager()
        assert mgr.get_credentials() == []

    def test_save_credentials(self):
        mgr = make_manager()
        m = mock_open()
        with patch("builtins.open", m):
            with patch("json.dump") as mock_dump:
                mgr.save_credentials(SAMPLE_CREDS)
        mock_dump.assert_called_once_with(SAMPLE_CREDS, m())


class TestCredentialsDraft:
    def _make_draft(self, creds=None):
        data = creds if creds is not None else SAMPLE_CREDS
        mock_mgr = MagicMock()
        mock_mgr.get_credentials.return_value = data
        with patch("finch.settings.credentials.manager.CredentialsManager", return_value=mock_mgr):
            return CredentialsDraft()

    def test_row_count(self):
        draft = self._make_draft()
        assert draft.row_count() == len(SAMPLE_CREDS)

    def test_get_value_name_column(self):
        draft = self._make_draft()
        name_col = next(i for i, (k, _) in enumerate(COLUMNS) if k == "name")
        assert draft.get_value(0, name_col) == "prod"

    def test_set_value_round_trip(self):
        draft = self._make_draft()
        name_col = next(i for i, (k, _) in enumerate(COLUMNS) if k == "name")
        draft.set_value(0, name_col, "new-name")
        assert draft.get_value(0, name_col) == "new-name"

    def test_insert_row_increments_count(self):
        draft = self._make_draft([])
        draft.insert_row()
        assert draft.row_count() == 1

    def test_insert_row_defaults(self):
        draft = self._make_draft([])
        draft.insert_row()
        name_col = next(i for i, (k, _) in enumerate(COLUMNS) if k == "name")
        assert draft.get_value(0, name_col) == ""

    def test_delete_row(self):
        draft = self._make_draft()
        draft.delete_row(0)
        assert draft.row_count() == len(SAMPLE_CREDS) - 1

    def test_secret_key_masked(self):
        draft = self._make_draft()
        secret_col = next(i for i, (k, _) in enumerate(COLUMNS) if k == "secret_key")
        assert draft.get_value(0, secret_col) == "xxx"
