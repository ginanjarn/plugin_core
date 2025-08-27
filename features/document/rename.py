from collections import namedtuple
from functools import wraps
from typing import Optional, Iterator
import sublime
import sublime_plugin

from ..workspace.edit import WorkspaceEdit
from ...document import is_valid_document
from ...message import Response
from ...session import Session
from ...uri import path_to_uri
from ....constant import COMMAND_PREFIX


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _PrepareRenameCommand(sublime_plugin.TextCommand):
    client = None

    @client_must_ready
    def run(self, edit: sublime.Edit, event: Optional[dict] = None):
        if not is_valid_document(self.view):
            return
        if event:
            point = event["text_point"]
        else:
            point = self.view.sel()[0].begin()

        start_row, start_col = self.view.rowcol(point)
        self.client.textdocument_preparerename(self.view, start_row, start_col)

    def is_visible(self):
        return is_valid_document(self.view)

    def want_event(self):
        return True


class _RenameCommand(sublime_plugin.TextCommand):
    client = None

    @client_must_ready
    def run(self, edit: sublime.Edit, row: int, column: int, new_name: str):
        if not is_valid_document(self.view):
            return
        self.client.textdocument_rename(self.view, row, column, new_name)

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


class DocumentRenameMixins:

    rename_target = None

    @must_initialized
    def textdocument_preparerename(self, view, row, col):
        if document := self.session.get_document(view.file_name()):
            self.rename_target = document
            self.message_pool.send_request(
                "textDocument/prepareRename",
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                },
            )

    def handle_textdocument_preparerename(self, session: Session, response: Response):
        if error := response.error:
            print(error["message"])
        elif result := response.result:
            self._prompt_rename(session, result)

    def _prompt_rename(self, session: Session, symbol_range: dict):
        view = self.rename_target.view

        start = LineCharacter(**symbol_range["range"]["start"])
        end = LineCharacter(**symbol_range["range"]["end"])
        start_point = view.text_point(*start)
        end_point = view.text_point(*end)

        region = sublime.Region(start_point, end_point)
        old_name = view.substr(region)
        row, col = view.rowcol(start_point)

        def request_rename(new_name):
            if new_name and old_name != new_name:
                view.run_command(
                    f"{COMMAND_PREFIX}_rename",
                    {"row": row, "column": col, "new_name": new_name},
                )

        view.window().show_input_panel(
            caption="Rename",
            initial_text=old_name,
            on_done=request_rename,
            on_change=None,
            on_cancel=None,
        )

    @must_initialized
    def textdocument_rename(self, view, row, col, new_name):
        # Save all changes before perform rename
        for document in self.session.get_documents():
            document.view.run_command("save")

        if document := self.session.get_document(view.file_name()):
            self.rename_target = document
            self.message_pool.send_request(
                "textDocument/rename",
                {
                    "newName": new_name,
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                },
            )

    def handle_textdocument_rename(self, session: Session, response: Response):
        if error := response.error:
            print(error["message"])
        elif result := response.result:
            changes = self._get_changes(result)
            WorkspaceEdit(session).apply_changes(changes)

    def _get_changes(self, edit: dict) -> Iterator[dict]:
        for document_changes in edit["documentChanges"]:
            yield document_changes
