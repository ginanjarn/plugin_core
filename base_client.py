"""RPC client implementation for Language Server"""

import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Optional

from .child_process import ChildProcess
from .lsprotocol.client import Client as LSClient
from .rpc import RPC, Context, Method, Result
from .transport import Transport

LOGGER = logging.getLogger(__name__)


class BaseClient(RPC, LSClient, ABC):
    """"""

    def __init__(
        self,
        process: ChildProcess,
        transport: Transport,
    ):
        super().__init__(transport)
        self.server_process = process

        self.set_client_capabilities()

    @abstractmethod
    def set_client_capabilities(self):
        """set client capabilities"""

    def _handle(
        self, context: Context, method: Method, param_or_result: Optional[Any] = None
    ) -> Optional[Result]:
        """_handle command"""
        # adapter for handle defined by LSClient
        self.handle(context, method, param_or_result)

    def shutdown(self) -> None:
        """Shutdown the server process."""
        try:
            self.shutdown_request(None)
            self.exit_notification(None)
        except Exception as err:
            LOGGER.warning("Error sending shutdown/exit: %s", err)
        finally:
            self.server_process.terminate()


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
