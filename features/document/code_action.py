from collections import namedtuple
from functools import wraps
from typing import List, Any
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...message import Response
from ...session import Session
from ...uri import path_to_uri


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

        self.client.textdocument_code_action(self.view, self.view.sel()[0], kinds)

    def is_visible(self):
        return is_valid_document(self.view)


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentCodeActionMixins:

    code_action_target = None

    @must_initialized
    def textdocument_code_action(self, view, region, action_kinds=None):
        if document := self.session.get_document(view.file_name()):
            self.code_action_target = document
            start = LineCharacter(*view.rowcol(region.begin()))
            end = LineCharacter(*view.rowcol(region.end()))
            diagnostis = self.session.diagnostic_manager.get_raw(view)

            context = {
                "diagnostics": diagnostis,
                "triggerKind": 2,
            }
            if action_kinds:
                context["only"] = list(action_kinds)

            self.message_pool.send_request(
                "textDocument/codeAction",
                {
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                    "range": {
                        "start": {"line": start.line, "character": start.character},
                        "end": {"line": end.line, "character": end.character},
                    },
                    "context": context,
                },
            )

    def handle_textdocument_code_action(self, session: Session, params: Response):
        if err := params.error:
            print(err["message"])

        elif result := params.result:
            self.show_action_panels(session, result)

    def show_action_panels(self, session: Session, code_actions: List[dict]):
        titles = [f"{act['title']} ({act['kind']})" for act in code_actions]

        def on_select_action(index=-1):
            if index < 0:
                return
            self._handle_selected_action(session, code_actions[index])

        sublime.active_window().show_quick_panel(
            titles,
            on_select=on_select_action,
            flags=sublime.MONOSPACE_FONT,
        )

    def _handle_selected_action(self, session: Session, action: dict) -> None:
        raise NotImplementedError


class CodeActionResolveMixins:

    @must_initialized
    def code_action_resolve(self, params: Any):
        self.message_pool.send_request("codeAction/resolve", params)

    def handle_code_action_resolve(self, session: Session, params: Response):
        if err := params.error:
            print(err["message"])

        elif result := params.result:
            self._handle_action(session, result)

    def _handle_action(self, session: Session, action: dict) -> None:
        raise NotImplementedError
