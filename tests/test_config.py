import json
from unittest.mock import mock_open, patch

from finch.config import ObjectType, Settings


class TestObjectType:
    def test_values_exist(self):
        assert ObjectType.BUCKET == "Bucket"
        assert ObjectType.FOLDER == "Folder"
        assert ObjectType.FILE == "File"

    def test_is_str(self):
        assert isinstance(ObjectType.BUCKET, str)


class TestSettingsDefaults:
    def test_defaults(self):
        s = Settings()
        assert s.check_folder_contents is True
        assert s.datetime_format == "%d %b %Y %H:%M"
        assert s.logging_enabled is False
        assert s.logging_to_file is False
        assert isinstance(s.logger_levels, dict)


class TestSettingsLoad:
    def test_load_updates_fields(self):
        data = {
            "check_folder_contents": False,
            "datetime_format": "%Y/%m/%d",
            "logging_enabled": True,
            "logging_to_file": False,
            "log_file_path": "/tmp/finch.log",
            "logger_levels": {},
        }
        s = Settings()
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            s.load()
        assert s.check_folder_contents is False
        assert s.datetime_format == "%Y/%m/%d"
        assert s.logging_enabled is True
        assert s.log_file_path == "/tmp/finch.log"

    def test_load_missing_file_keeps_defaults(self):
        s = Settings()
        with patch("builtins.open", side_effect=FileNotFoundError):
            s.load()
        assert s.check_folder_contents is True
        assert s.logging_enabled is False

    def test_load_bad_json_keeps_defaults(self):
        s = Settings()
        with patch("builtins.open", mock_open(read_data="not json")):
            s.load()
        assert s.check_folder_contents is True


class TestSettingsSave:
    def test_save_writes_json(self):
        s = Settings()
        m = mock_open()
        with patch("builtins.open", m):
            with patch("json.dump") as mock_dump:
                s.save()
        mock_dump.assert_called_once()
        saved = mock_dump.call_args[0][0]
        assert saved["check_folder_contents"] == s.check_folder_contents
        assert saved["datetime_format"] == s.datetime_format
        assert "logger_levels" in saved
