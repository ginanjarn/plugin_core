import logging
from typing import Iterator

from ...lsprotocol.client import (
    Client,
    ApplyWorkspaceEditParams,
    ApplyWorkspaceEditResult,
)
from ...features.document_updater import Workspace
from ....constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)
PathStr = str


class WorkspaceApplyEditMixins(Client):
    def handle_apply_workspace_edit_request(
        self, context: dict, params: ApplyWorkspaceEditParams
    ) -> ApplyWorkspaceEditResult:
        try:
            changes = self._get_document_changes(params["edit"])
            Workspace(self.session).apply_document_changes(changes)

        except Exception as err:
            LOGGER.error(err, exc_info=True)
            return {"applied": False}
        else:
            return {"applied": True}

    def _get_document_changes(self, workspace_edit: dict) -> Iterator[dict]:
        for changes in workspace_edit["documentChanges"]:
            yield changes
