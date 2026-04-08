from datetime import datetime

import pytest

from finch.utils.text import (
    format_datetime,
    format_list_with_conjunction,
    format_size,
    key_display_name,
)


class TestKeyDisplayName:
    def test_file_key(self):
        assert key_display_name("folder/file.txt") == "file.txt"

    def test_folder_key_trailing_slash(self):
        assert key_display_name("folder/subfolder/") == "subfolder"

    def test_root_key(self):
        assert key_display_name("file.txt") == "file.txt"

    def test_empty_string(self):
        # empty string splits into ['', ''] - returns parts[-2] == ''
        assert key_display_name("") == ""


class TestFormatSize:
    def test_zero_bytes(self):
        result = format_size(0)
        assert "Bytes" in result
        assert "0" in result

    def test_bytes(self):
        result = format_size(512)
        assert "Bytes" in result

    def test_kilobytes(self):
        result = format_size(2048)
        assert "Kilobytes" in result

    def test_megabytes(self):
        result = format_size(2 * 1024 * 1024)
        assert "Megabytes" in result

    def test_gigabytes(self):
        result = format_size(2 * 1024 * 1024 * 1024)
        assert "Gigabytes" in result

    def test_trailing_zeros_stripped(self):
        result = format_size(1024)
        assert "1 Kilobytes" in result

    def test_decimal_places(self):
        result = format_size(1536, decimal_places=1)
        assert "1.5 Kilobytes" in result


class TestFormatListWithConjunction:
    def test_empty(self):
        assert format_list_with_conjunction([]) == ""

    def test_single(self):
        assert format_list_with_conjunction(["a"]) == "a"

    def test_two_items(self):
        assert format_list_with_conjunction(["a", "b"]) == "a and b"

    def test_three_items(self):
        assert format_list_with_conjunction(["a", "b", "c"]) == "a, b and c"

    def test_custom_conjunction(self):
        assert format_list_with_conjunction(["a", "b"], conjunction="or") == "a or b"


class TestFormatDatetime:
    def test_none_returns_empty(self):
        assert format_datetime(None) == ""

    def test_formats_with_app_settings(self, mocker):
        mocker.patch("finch.utils.text.app_settings.datetime_format", "%Y-%m-%d")
        dt = datetime(2024, 1, 15, 10, 30)
        assert format_datetime(dt) == "2024-01-15"

    def test_default_format(self):
        dt = datetime(2024, 1, 15, 10, 30)
        result = format_datetime(dt)
        assert result != ""
        assert "2024" in result or "15" in result
