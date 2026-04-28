from functools import wraps
from typing import Union
import logging
import sublime_plugin

from ...client_internal import BaseClient
from ...lsprotocol.client import LSPAny
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class WorkspaceExecuteCommandMixins(BaseClient):

    def workspace_executecommand(self, commands: dict):
        self.execute_command_request(commands)

    def handle_execute_command_result(
        self, context: dict, result: Union[LSPAny, None]
    ) -> None:
        if not result:
            return
        LOGGER.info(result)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _WorkspaceExecuteCommandCommand(sublime_plugin.WindowCommand):
    client: WorkspaceExecuteCommandMixins = None

    @client_must_ready
    def run(self, command: dict):
        self.client.workspace_executecommand(command)

    def is_visible(self):
        return self.client and self.client.is_ready()
