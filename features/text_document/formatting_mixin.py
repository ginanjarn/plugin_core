from typing import List, Optional, Union

import sublime

from ...document import Document
from ...lsprotocol.client import TextEdit
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ..base_feature import BaseFeature, require_server_capability
from ..workspace_updater import apply_text_edits


class DocumentFormattingMixin(BaseFeature):
    """Handles document formatting requests and results."""

    document_formatting_target: Optional[Document]

    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["textDocument"].update(
            {"formatting": {"dynamicRegistration": False}}
        )

    @on_new_thread
    @require_server_capability("documentFormattingProvider")
    def textdocument_formatting(self, view: sublime.View) -> None:

        document = self.session.get_document(view)
        if document:
            self.document_formatting_target = document
            sublime.status_message("LSP: Formatting document...")
            self.document_formatting_request(
                {"textDocument": {"uri": path_to_uri(document.file_name)}}
            )

    @on_main_thread
    def handle_document_formatting_result(
        self, context: dict, result: Union[List[TextEdit], None]
    ) -> None:
        if not (result and self.document_formatting_target):
            sublime.status_message("LSP: No formatting changes")
            return
        try:
            apply_text_edits(
                self.session,
                self.client_options,
                self.document_formatting_target.file_name,
                result,
            )
            sublime.status_message("LSP: Document formatted")
        except Exception as e:
            print(f"[LSP Formatting] Error applying edits: {e}")
            sublime.status_message("LSP: Formatting failed")
