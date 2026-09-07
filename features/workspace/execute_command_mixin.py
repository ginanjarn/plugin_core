import logging
from typing import Union

from ...client_internal import BaseClient
from ...lsprotocol.client import LSPAny
from ...utils import on_main_thread, on_new_thread

LOGGER = logging.getLogger(__name__)


class WorkspaceExecuteCommandMixin(BaseClient):
    def set_client_capabilities(self):
        self.session.client_capabilities["workspace"].update(
            {"executeCommand": {"dynamicRegistration": False}}
        )

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
