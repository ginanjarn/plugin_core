""""""

from functools import wraps
from typing import Optional
from ..client_internal import BaseClient


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
