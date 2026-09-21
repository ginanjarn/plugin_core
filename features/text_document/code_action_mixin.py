from typing import List, Optional, Union

import sublime

from ..workspace_updater import apply_workspace_edit
from ...client_internal import BaseClient, require_server_capability
from ...document import Document
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import Command, CodeAction


class DocumentCodeActionMixin(BaseClient):

    document_code_action_target: Optional[Document] = None

    def set_client_capabilities(self):
        self.session.client_capabilities["textDocument"].update(
            {
                "codeAction": {
                    "dynamicRegistration": False,
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": [
                                "",
                                "quickfix",
                                "refactor",
                                "refactor.extract",
                                "refactor.inline",
                                "refactor.move",
                                "refactor.rewrite",
                                "source",
                                "source.organizeImports",
                                "source.fixAll",
                                "notebook",
                            ]
                        }
                    },
                    "isPreferredSupport": False,
                    "disabledSupport": False,
                    "dataSupport": False,
                    "resolveSupport": {"properties": []},
                    "honorsChangeAnnotations": False,
                    "documentationSupport": False,
                    "tagSupport": {"valueSet": [1]},
                }
            }
        )

    @on_new_thread
    @require_server_capability("codeActionProvider")
    def textdocument_codeaction(
        self,
        view: sublime.View,
        region: sublime.Region,
        code_action_kinds: Optional[List[str]] = None,
    ):
        if document := self.session.get_document(view):
            self.document_code_action_target = document
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

    @on_main_thread
    def handle_code_action_result(
        self, context: dict, result: Union[List[Union[Command, CodeAction]], None]
    ) -> None:
        if not (result and self.document_code_action_target):
            return

        def build_title(action: Union[Command, CodeAction]):
            title = action["title"]
            if kind := action.get("kind"):
                return f"{title} ({kind})"
            return f"{title}"

        titles = [build_title(act) for act in result]

        def on_select_action(index=-1):
            if index < 0:
                return
            self._handle_code_action(context, result[index])

        sublime.active_window().show_quick_panel(
            titles,
            on_select=on_select_action,
            flags=sublime.MONOSPACE_FONT,
        )

    def _handle_code_action(
        self, context: dict, action: Union[Command, CodeAction]
    ) -> None:
        if edit := action.get("edit"):
            apply_workspace_edit(self.session, edit)
        elif command := action.get("command"):
            if isinstance(command, str):
                # action type is Command
                command = action
            self.workspace_executecommand(command)
        else:
            self.codeaction_resolve(action)

    def codeaction_resolve(self, params: CodeAction):
        self.code_action_resolve_request(params)

    def handle_code_action_resolve_result(
        self, context: dict, result: CodeAction
    ) -> None:
        if not result:
            return
        self._handle_code_action(self.session, result)
