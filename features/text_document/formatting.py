from functools import wraps
from typing import List, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...features.workspace.workspace_edit import WorkspaceEdit
from ...uri import path_to_uri
from ...lsprotocol.client import Client, TextEdit


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
        if not self.session.server_capabilities.get("documentFormattingProvider", False):
            return
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
        WorkspaceEdit(self.session).apply_text_edit(
            self.formatting_target.file_name, result
        )


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _DocumentFormattingCommand(sublime_plugin.TextCommand):
    client: DocumentFormattingMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit):
        if not is_valid_document(self.view):
            return
        self.client.textdocument_formatting(self.view)

    def is_visible(self):
        return is_valid_document(self.view)
