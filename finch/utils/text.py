from datetime import datetime
from typing import Union

from finch.config import app_settings


def key_display_name(key: str) -> str:
    """Return the last path segment of an S3 key for display."""
    parts = [p for p in key.split('/') if p]
    return parts[-1] if parts else ''


def format_datetime(dt: datetime) -> str:
    if dt:
        return dt.strftime(app_settings.datetime_format)
    return ''


def _remove_trailing_zeros(x: str) -> str:
    return x.rstrip('0').rstrip('.')


def format_size(file_size: Union[int, float], decimal_places=2) -> str:
    for unit in ['Bytes', 'Kilobytes', 'Megabytes', 'Gigabytes']:
        if file_size < 1024.0 or unit == 'Gigabytes':
            break
        file_size /= 1024.0
    return f'{_remove_trailing_zeros(f"{file_size:.{decimal_places}f}"): >8} {unit}'


def format_list_with_conjunction(items: list, conjunction='and') -> str:
    if len(items) > 1:
        return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"
    return items[0] if items else ''