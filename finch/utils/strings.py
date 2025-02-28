from datetime import datetime
from typing import Union

DATETIME_FORMAT = "%d %b %Y %H:%M"


def format_object_name(filename: str) -> str:
    """ Function for getting file and folder names from full object path"""
    arr = filename.split('/')
    if arr[-1]:
        return arr[-1]
    else:
        return arr[-2]


def format_datetime(dt: datetime) -> str:
    """ Function for format dates """
    if dt:
        return dt.strftime(DATETIME_FORMAT)
    else:
        return ''


def remove_trailing_zeros(x: str) -> str:
    """ Function for removing trailing zeros from floats """
    return x.rstrip('0').rstrip('.')


def format_size(file_size: Union[int, float], decimal_places=2) -> str:
    """ Function for formatting file sizes to human-readable forms """
    for unit in ['Bytes', 'Kilobytes', 'Megabytes', 'Gigabytes']:
        if file_size < 1024.0 or unit == 'Gigabytes':
            break
        file_size /= 1024.0
    return f'{remove_trailing_zeros(f"{file_size:.{decimal_places}f}"): >8} {unit}'


def format_list_with_conjunction(items: list, conjunction='and', seperator=', ', add_quotes=False) -> str:
    """Format list items with proper punctuation and conjunction.
    Example: ['a', 'b', 'c'] -> 'a, b and c'"""
    quote = lambda _items: list(map(lambda _item: f'"{_item}"', _items))
    items = quote(items) if add_quotes else items
    if len(items) > 1:
        return f"{seperator.join(items[:-1])} {conjunction} {items[-1]}"
    return items[0] if items else ''
