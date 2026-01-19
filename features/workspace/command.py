from functools import wraps
from typing import Union
import logging

from ....constant import LOGGING_CHANNEL
from ...lsprotocol.client import Client, LSPAny

LOGGER = logging.getLogger(LOGGING_CHANNEL)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class WorkspaceExecuteCommandMixins(Client):

    def workspace_executecommand(self, commands: dict):
        self.execute_command_request(commands)

    def handle_execute_command_result(
        self, context: dict, result: Union[LSPAny, None]
    ) -> None:
        if not result:
            return
        LOGGER.info(result)
