from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Optional

from ..lsprotocol.client import Client as LSClient
from ..message import Method, Result
from ..rpc import Context
from ..options import ClientOptions
from ..session import Session


class BaseFeature(LSClient, ABC):
    session: Session
    client_name: str
    client_options: ClientOptions

    @abstractmethod
    def set_client_capabilities(self):
        """"""

    def _handle(
        self, context: Context, method: Method, param_or_result: Optional[Any] = None
    ) -> Optional[Result]:
        """_handle command"""
        # adapter for handle defined by LSClient
        self.handle(context, method, param_or_result)


def require_server_capability(capability: str):
    """call function if required capability satisfied"""

    def inner_fn(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.session.server_capabilities.get(capability):
                return func(self, *args, **kwargs)
            return None

        return wrapper

    return inner_fn
