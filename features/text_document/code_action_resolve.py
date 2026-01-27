from functools import wraps
from typing import Any

from ...features.workspace.workspace_edit import WorkspaceEdit
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
            WorkspaceEdit(self.session).apply(edit)
        if command := action.get("command"):
            self.workspace_executecommand(command)
