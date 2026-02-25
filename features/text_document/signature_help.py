from collections import namedtuple
from functools import wraps
from typing import Union
import sublime
import sublime_plugin

from ....constant import LANGUAGE_ID
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
        capabilities = self.session.server_capabilities.get("signatureHelpProvider", {})
        if not capabilities:
            return
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

        content = "".join(
            [
                f"```{LANGUAGE_ID}\n",
                "\n".join([s["label"] for s in signatures]),
                "\n```",
            ]
        )
        view = self.signature_help_target.view
        location = view.sel()[0].a
        self.show_signature_popup(view, content, location, "markdown")

    @staticmethod
    def show_signature_popup(view: sublime.View, text: str, location: int, markup: str):
        view.run_command(
            "marked_popup",
            {
                "location": location,
                "text": text,
                "markup": markup,
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
        self.client.textdocument_signaturehelp(self.view, row, column)


class DocumentSignatureHelpEventListener(sublime_plugin.EventListener):
    client: DocumentSignatureHelpMixins = None
    _trigger_characters = []
    insert_commands = {"insert", "insert_snippet", "insert_completion"}

    @client_must_ready
    def on_modified_async(self, view: sublime.View) -> None:
        if not is_valid_document(view):
            return

        name, *_ = view.command_history(0)
        if name not in self.insert_commands:
            return

        point = view.sel()[0].begin()
        char = view.substr(point - 1)
        if char in self.trigger_characters:
            row, column = view.rowcol(point)
            self.client.textdocument_signaturehelp(view, row, column)

    @property
    def trigger_characters(self) -> str:
        if self._trigger_characters:
            return self._trigger_characters

        try:
            capabilities = self.client.session.server_capabilities
            chars = capabilities["signatureHelpProvider"]["triggerCharacters"]
        except (KeyError, AttributeError):
            chars = ["("]

        self._trigger_characters = chars
        return self._trigger_characters
