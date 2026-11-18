import logging
from typing import Union

from ...lsprotocol.client import LSPAny
from ...utils import on_main_thread, on_new_thread
from ..base_feature import BaseFeature

LOGGER = logging.getLogger(__name__)


class WorkspaceExecuteCommandMixin(BaseFeature):
    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["workspace"].update(
            {"executeCommand": {"dynamicRegistration": False}}
        )

    @on_new_thread
    def workspace_executecommand(self, command: dict):
        self.execute_command_request(command)

    @on_main_thread
    def handle_execute_command_result(
        self, context: dict, result: Union[LSPAny, None]
    ) -> None:
        if not result:
            return
        LOGGER.info(result)
