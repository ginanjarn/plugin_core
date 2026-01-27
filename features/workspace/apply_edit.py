import logging

from ...lsprotocol.client import (
    Client,
    ApplyWorkspaceEditParams,
    ApplyWorkspaceEditResult,
)
from ...features.workspace.workspace_edit import WorkspaceEdit
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class WorkspaceApplyEditMixins(Client):
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
