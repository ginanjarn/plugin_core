from collections import namedtuple
from functools import wraps
from typing import Union
import sublime
import sublime_plugin

from ....constant import COMMAND_PREFIX, LANGUAGE_ID
from ...document import is_valid_document
from ...uri import path_to_uri
from ...lsprotocol.client import Client, SignatureHelp


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentSignatureHelpMixins(Client):

    signature_help_target = None

    @must_initialized
    def textdocument_signaturehelp(self, view: sublime.View, row: int, col: int):
        if document := self.session.get_document(view):
            self.signature_help_target = document
            self.signature_help_request(
                {
                    "position": {"line": row, "character": col},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                },
            )

    def handle_signature_help_result(
        self, context: dict, result: Union[SignatureHelp, None]
    ) -> None:
        if not result:
            return
        signatures = result["signatures"]
        if not signatures:
            return

        message = "".join(
            [
                f"```{LANGUAGE_ID}\n",
                "\n".join([s["label"] for s in signatures]),
                "\n```",
            ]
        )
        view = self.signature_help_target.view
        row, col = view.rowcol(view.sel()[0].a)
        self.show_popup(view, message, row, col)

    @staticmethod
    def show_popup(
        view: sublime.View,
        text: str,
        row: int,
        col: int,
        keep_visible: bool = False,
    ):
        point = view.text_point(row, col)
        view.run_command(
            "marked_popup",
            {
                "location": point,
                "text": text,
                "markup": "markdown",
                "keep_visible": keep_visible,
            },
        )


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _DocumentSignatureHelpCommand(sublime_plugin.TextCommand):
    client: DocumentSignatureHelpMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit):
        if not is_valid_document(self.view):
            return

        point = self.view.sel()[0].begin()
        row, column = self.view.rowcol(point)
        if not self.view.match_selector(point, "meta.function-call.arguments"):
            return

        self.client.textdocument_signaturehelp(self.view, row, column)


class DocumentSignatureHelpEventListener(sublime_plugin.EventListener):
    client = None

    @client_must_ready
    def on_modified_async(self, view: sublime.View):
        self.trigger_signature_help(view)

    def trigger_signature_help(self, view: sublime.View):
        if not is_valid_document(view):
            return
        point = view.sel()[0].begin()
        if view.substr(point - 1) in {"(", ","}:
            view.run_command(f"{COMMAND_PREFIX}_document_signature_help")
