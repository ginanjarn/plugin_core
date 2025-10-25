from functools import wraps
from typing import Any, Iterator

from ...message import Response
from ...session import Session
from ...features.document_updater import Workspace


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class CodeActionResolveMixins:

    @must_initialized
    def codeaction_resolve(self, params: Any):
        self.request_codeaction_resolve(params)

    def request_codeaction_resolve(self, params: dict):
        self.message_pool.send_request("codeAction/resolve", params)

    def handle_codeaction_resolve(self, session: Session, response: Response):
        if err := response.error:
            print(err["message"])

        elif result := response.result:
            self._handle_action(session, result)

    def _handle_action(self, session: Session, action: dict) -> None:
        if edit := action.get("edit"):
            changes = self._get_document_changes(edit)
            Workspace(session).apply_document_changes(changes)
        if command := action.get("command"):
            self.workspace_executecommand(command)

    def _get_document_changes(self, workspace_edit: dict) -> Iterator[dict]:
        for changes in workspace_edit["documentChanges"]:
            yield changes
