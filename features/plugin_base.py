""""""

from functools import wraps
from typing import Optional
import sublime

from ..client_internal import BaseClient
from ...constant import VIEW_SELECTOR


class PluginBase:
    """plugin base class"""

    client: Optional[BaseClient] = None


def client_must_ready(func):
    """client must ready to call function"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


def is_valid_document(view: sublime.View) -> bool:
    """check if view is valid document"""
    return bool(view.file_name()) and view.match_selector(0, VIEW_SELECTOR)


def must_valid_document(func):
    """document must valid to call function"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if is_valid_document(self.view):
            return func(self, *args, **kwargs)
        return None

    return wrapper
