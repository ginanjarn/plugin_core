import logging

from ..workspace_updater import apply_workspace_edit
from ...client_internal import BaseClient
from ...lsprotocol.client import ApplyWorkspaceEditParams, ApplyWorkspaceEditResult
from ...utils import on_main_thread
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class WorkspaceApplyEditMixins(BaseClient):
    @on_main_thread
    def handle_apply_workspace_edit_request(
        self, context: dict, params: ApplyWorkspaceEditParams
    ) -> ApplyWorkspaceEditResult:
        try:
            apply_workspace_edit(self.session, params["edit"])
        except Exception as err:
            LOGGER.error(err, exc_info=True)
            return {"applied": False}
        else:
            return {"applied": True}
