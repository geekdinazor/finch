import asyncio
import functools


def async_slot(fn):
    """Decorator: makes an async method callable as a Qt signal slot.

    Schedules the coroutine with asyncio.ensure_future so it can be
    connected to signals and called from sync contexts.
    """
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        asyncio.ensure_future(fn(self, *args, **kwargs))
    return wrapper