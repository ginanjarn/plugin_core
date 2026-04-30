from typing import Union
import logging
import sublime_plugin

from ...client_internal import BaseClient
from ...lsprotocol.client import LSPAny
from ...utils import client_must_ready, on_main_thread, on_new_thread
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class WorkspaceExecuteCommandMixins(BaseClient):

    @on_new_thread
    def workspace_executecommand(self, commands: dict):
        self.execute_command_request(commands)

    @on_main_thread
    def handle_execute_command_result(
        self, context: dict, result: Union[LSPAny, None]
    ) -> None:
        if not result:
            return
        LOGGER.info(result)


class _WorkspaceExecuteCommandCommand(sublime_plugin.WindowCommand):
    client: WorkspaceExecuteCommandMixins = None

    @client_must_ready
    def run(self, command: dict):
        self.client.workspace_executecommand(command)

    def is_visible(self):
        return self.client and self.client.is_ready()
