from functools import wraps
from typing import List, Optional, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...uri import path_to_uri
from ...features.workspace.workspace_edit import WorkspaceEdit
from ...lsprotocol.client import Client, Command, CodeAction


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
        code_action_kinds: Optional[List[str]] = None,
    ):
        if not self.session.server_capabilities.get("codeActionProvider", False):
            return
        if document := self.session.get_document(view):
            self.code_action_target = document
            start = view.rowcol(region.begin())
            end = view.rowcol(region.end())

            context = {
                "diagnostics": document.diagnostics,
                "triggerKind": 2,
            }
            if code_action_kinds:
                context["only"] = list(code_action_kinds)

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

        code_actions = result

        def build_title(action: Union[Command, CodeAction]):
            title = action["title"]
            if kind := action.get("kind"):
                return f"{title} ({kind})"
            return f"{title}"

        titles = [build_title(act) for act in code_actions]

        def on_select_action(index=-1):
            if index < 0:
                return
            self._handle_code_action(context, code_actions[index])

        sublime.active_window().show_quick_panel(
            titles,
            on_select=on_select_action,
            flags=sublime.MONOSPACE_FONT,
        )

    def _handle_code_action(
        self, context: dict, action: Union[Command, CodeAction]
    ) -> None:
        if edit := action.get("edit"):
            WorkspaceEdit(self.session).apply(edit)
        elif command := action.get("command"):
            self.workspace_executecommand(command)
        else:
            self.codeaction_resolve(action)

    @must_initialized
    def codeaction_resolve(self, params: CodeAction):
        self.code_action_resolve_request(params)

    def handle_code_action_resolve_result(
        self, context: dict, result: CodeAction
    ) -> None:
        if not result:
            return
        self._handle_code_action(self.session, result)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _CodeActionCommand(sublime_plugin.TextCommand):
    client: DocumentCodeActionMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit, kinds: List[str] = None):
        if not is_valid_document(self.view):
            return

        self.client.textdocument_codeaction(self.view, self.view.sel()[0], kinds)

    def is_visible(self):
        return is_valid_document(self.view)
