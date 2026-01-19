from collections import namedtuple
from dataclasses import asdict
from functools import wraps
from typing import List, Union
import sublime
import sublime_plugin

from ....constant import COMMAND_PREFIX
from ...document import is_valid_document, TextChange
from ...uri import path_to_uri
from ...lsprotocol.client import Client, TextEdit


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _DocumentFormattingCommand(sublime_plugin.TextCommand):
    client = None

    @client_must_ready
    def run(self, edit: sublime.Edit):
        if not is_valid_document(self.view):
            return
        self.client.textdocument_formatting(self.view)

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


class DocumentFormattingMixins(Client):

    formatting_target = None

    @must_initialized
    def textdocument_formatting(self, view: sublime.View):
        if document := self.session.get_document(view):
            self.formatting_target = document
            self.document_formatting_request(
                {"textDocument": {"uri": path_to_uri(document.file_name)}}
            )

    def handle_document_formatting_result(
        self, context: dict, result: Union[List[TextEdit], None]
    ) -> None:
        if not result:
            return
        changes = [rpc_to_textchange(c) for c in result]
        self.apply_view_changes(self.formatting_target.view, changes)

    @staticmethod
    def apply_view_changes(view: sublime.View, text_changes: List[TextChange]):
        view.run_command(
            f"{COMMAND_PREFIX}_apply_text_changes",
            {"changes": [asdict(c) for c in text_changes]},
        )


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def rpc_to_textchange(change: dict) -> TextChange:
    """"""
    return TextChange(
        LineCharacter(**change["range"]["start"]),
        LineCharacter(**change["range"]["end"]),
        change["newText"],
        change.get("rangeLength", 0),
    )
