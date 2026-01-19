from functools import wraps
from typing import List, Optional, Iterator, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...uri import path_to_uri
from ...features.document_updater import Workspace
from ...lsprotocol.client import Client, Command, CodeAction


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _CodeActionCommand(sublime_plugin.TextCommand):
    client = None

    @client_must_ready
    def run(self, edit: sublime.Edit, kinds: List[str] = None):
        if not is_valid_document(self.view):
            return

        self.client.textdocument_codeaction(self.view, self.view.sel()[0], kinds)

    def is_visible(self):
        return is_valid_document(self.view)


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentCodeActionMixins(Client):

    code_action_target = None

    @must_initialized
    def textdocument_codeaction(
        self,
        view: sublime.View,
        region: sublime.Region,
        action_kinds: Optional[List[int]] = None,
    ):
        if document := self.session.get_document(view):
            self.code_action_target = document
            start = view.rowcol(region.begin())
            end = view.rowcol(region.end())

            context = {
                "diagnostics": document.diagnostics,
                "triggerKind": 2,
            }
            if action_kinds:
                context["only"] = list(action_kinds)

            self.code_action_request(
                {
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                    "range": {
                        "start": {"line": start[0], "character": start[1]},
                        "end": {"line": end[0], "character": end[1]},
                    },
                    "context": context,
                },
            )

    def handle_code_action_result(
        self, context: dict, result: Union[List[Union[Command, CodeAction]], None]
    ) -> None:
        if not result:
            return
        self.show_action_panels(self.session, result)

    def show_action_panels(self, context: dict, code_actions: List[dict]):
        titles = [f"{act['title']} ({act['kind']})" for act in code_actions]

        def on_select_action(index=-1):
            if index < 0:
                return
            self._handle_selected_action(self.session, code_actions[index])

        sublime.active_window().show_quick_panel(
            titles,
            on_select=on_select_action,
            flags=sublime.MONOSPACE_FONT,
        )

    def _handle_selected_action(self, context: dict, action: dict) -> None:
        if edit := action.get("edit"):
            changes = self._get_document_changes(edit)
            Workspace(self.session).apply_document_changes(changes)
        if command := action.get("command"):
            self.workspace_executecommand(command)

    def _get_document_changes(self, workspace_edit: dict) -> Iterator[dict]:
        for changes in workspace_edit["documentChanges"]:
            yield changes
