from typing import List, Union
import sublime
import sublime_plugin

from ...client_internal import BaseClient
from ...document import is_valid_document
from ...features.workspace.workspace_edit import WorkspaceEdit
from ...uri import path_to_uri
from ...utils import client_must_ready, on_main_thread, on_new_thread
from ...lsprotocol.client import TextEdit


class DocumentFormattingMixins(BaseClient):

    formatting_target = None

    @on_new_thread
    def textdocument_formatting(self, view: sublime.View):
        if not self.session.server_capabilities.get(
            "documentFormattingProvider", False
        ):
            return
        if document := self.session.get_document(view):
            self.formatting_target = document
            self.document_formatting_request(
                {"textDocument": {"uri": path_to_uri(document.file_name)}}
            )

    @on_main_thread
    def handle_document_formatting_result(
        self, context: dict, result: Union[List[TextEdit], None]
    ) -> None:
        if not result:
            return
        WorkspaceEdit(self.session).apply_text_edit(
            self.formatting_target.file_name, result
        )


class _DocumentFormattingCommand(sublime_plugin.TextCommand):
    client: DocumentFormattingMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit):
        if not is_valid_document(self.view):
            return
        self.client.textdocument_formatting(self.view)

    def is_visible(self):
        return is_valid_document(self.view)
