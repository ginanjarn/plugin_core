import logging

from ...client_internal import BaseClient
from ...features.workspace.workspace_edit import WorkspaceEdit
from ...lsprotocol.client import ApplyWorkspaceEditParams, ApplyWorkspaceEditResult
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class WorkspaceApplyEditMixins(BaseClient):
    def handle_apply_workspace_edit_request(
        self, context: dict, params: ApplyWorkspaceEditParams
    ) -> ApplyWorkspaceEditResult:
        try:
            WorkspaceEdit(self.session).apply(params["edit"])
        except Exception as err:
            LOGGER.error(err, exc_info=True)
            return {"applied": False}
        else:
            return {"applied": True}
