import logging
from typing import Any, Dict

from ...lsprotocol.client import ApplyWorkspaceEditParams, ApplyWorkspaceEditResult
from ...utils import on_main_thread
from ..base_feature import BaseFeature
from ..workspace_updater import apply_workspace_edit

LOGGER = logging.getLogger(__name__)


class WorkspaceApplyEditMixin(BaseFeature):
    """
    Handle workspace/applyEdit requests from the server.

    Returns an ApplyWorkspaceEditResult-like dict:
      - applied: bool
      - failureReason: optional str (when applied is False)
      - failedChange: optional object (when available)
    """

    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["workspace"].update(
            {
                "applyEdit": True,
                "workspaceEdit": {
                    "documentChanges": True,
                    "resourceOperations": ["create", "rename", "delete"],
                    "failureHandling": "abort",
                    "normalizesLineEndings": True,
                    "changeAnnotationSupport": {"groupsOnLabel": False},
                    "metadataSupport": False,
                    "snippetEditSupport": False,
                },
            }
        )

    @on_main_thread
    def handle_apply_workspace_edit_request(
        self, context: Dict[str, Any], params: ApplyWorkspaceEditParams
    ) -> ApplyWorkspaceEditResult:
        # Validate incoming params
        if not isinstance(params, dict):
            LOGGER.error("applyWorkspaceEdit: invalid params type: %s", type(params))
            return {"applied": False, "failureReason": "Invalid params"}

        edit = params.get("edit")
        if not edit:
            LOGGER.warning("applyWorkspaceEdit: missing 'edit' in params")
            return {"applied": False, "failureReason": "Missing edit payload"}

        try:
            # apply_workspace_edit is expected to raise on failure
            apply_workspace_edit(self.session, self.client_options, edit)
        except Exception as err:
            # Log full traceback for diagnostics
            LOGGER.error("applyWorkspaceEdit failed: %s", err, exc_info=True)

            # Try to provide a concise failure reason for the server
            reason = str(err) or "Unknown error applying workspace edit"
            # Optionally include the edit or part of it as failedChange if small
            failed_change = None
            try:
                # Avoid returning huge payloads back to the server
                if isinstance(edit, dict):
                    # include a small summary rather than the full edit
                    failed_change = {
                        "summary": {
                            "documentChanges": bool(edit.get("documentChanges")),
                            "changes_keys": list(edit.get("changes", {}).keys())[:5],
                        }
                    }
            except Exception:
                failed_change = None

            result: ApplyWorkspaceEditResult = {
                "applied": False,
                "failureReason": reason,
            }
            if failed_change:
                result["failedChange"] = failed_change
            return result
        else:
            LOGGER.debug("applyWorkspaceEdit applied successfully")
            return {"applied": True}
