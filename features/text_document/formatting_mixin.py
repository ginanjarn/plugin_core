from typing import List, Union, Optional

import sublime

from ..workspace_updater import apply_text_edits
from ...client_internal import BaseClient
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import TextEdit


class DocumentFormattingMixin(BaseClient):
    """Handles document formatting requests and results."""

    formatting_target: Optional[object] = None

    @on_new_thread
    def textdocument_formatting(self, view: sublime.View) -> None:
        if not self.session.server_capabilities.get("documentFormattingProvider"):
            sublime.status_message("LSP: Formatting not supported by server")
            return
        document = self.session.get_document(view)
        if document:
            self.formatting_target = document
            sublime.status_message("LSP: Formatting document...")
            self.document_formatting_request(
                {"textDocument": {"uri": path_to_uri(document.file_name)}}
            )

    @on_main_thread
    def handle_document_formatting_result(
        self, context: dict, result: Union[List[TextEdit], None]
    ) -> None:
        if not result or not self.formatting_target:
            sublime.status_message("LSP: No formatting changes")
            return
        try:
            apply_text_edits(self.session, self.formatting_target.file_name, result)
            sublime.status_message("LSP: Document formatted")
        except Exception as e:
            print(f"[LSP Formatting] Error applying edits: {e}")
            sublime.status_message("LSP: Formatting failed")
        finally:
            self.formatting_target = None
