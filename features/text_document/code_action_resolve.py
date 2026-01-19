from functools import wraps
from typing import Any, Iterator

from ...features.document_updater import Workspace
from ...lsprotocol.client import Client, CodeAction


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class CodeActionResolveMixins(Client):

    @must_initialized
    def codeaction_resolve(self, params: Any):
        self.code_action_resolve_request(params)

    def handle_code_action_resolve_result(
        self, context: dict, result: CodeAction
    ) -> None:
        if not result:
            return
        self._handle_action(self.session, result)

    def _handle_action(self, context: dict, action: CodeAction) -> None:
        if edit := action.get("edit"):
            changes = self._get_document_changes(edit)
            Workspace(self.session).apply_document_changes(changes)
        if command := action.get("command"):
            self.workspace_executecommand(command)

    def _get_document_changes(self, workspace_edit: dict) -> Iterator[dict]:
        for changes in workspace_edit["documentChanges"]:
            yield changes
