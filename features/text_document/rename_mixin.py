from collections import namedtuple
from typing import Optional, Union, Dict, Any

import sublime

from ..workspace_updater import apply_workspace_edit
from ...client_internal import BaseClient, require_server_capability
from ...document import Document
from ...uri import path_to_uri
from ...lsprotocol.client import PrepareRenameResult, WorkspaceEdit as LspWorkspaceEdit
from ...utils import on_main_thread, on_new_thread

LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class DocumentRenameMixin(BaseClient):
    """Handle LSP prepareRename and rename requests with safer defaults and UX."""

    document_rename_target: Optional[Document] = None

    def set_client_capabilities(self):
        self.session.client_capabilities["textDocument"].update(
            {
                "rename": {
                    "dynamicRegistration": False,
                    "prepareSupport": True,
                    "prepareSupportDefaultBehavior": 1,
                    "honorsChangeAnnotations": False,
                }
            }
        )

    @on_new_thread
    @require_server_capability("renameProvider")
    def textdocument_preparerename(
        self, view: sublime.View, row: int, col: int
    ) -> None:
        """Ask server whether rename is allowed at the given position."""

        document = self.session.get_document(view)
        if not document:
            return

        self.document_rename_target = document
        self.prepare_rename_request(
            {
                "position": {"character": col, "line": row},
                "textDocument": {"uri": path_to_uri(document.file_name)},
            },
        )

    @on_main_thread
    def handle_prepare_rename_result(
        self, context: Dict[str, Any], result: Union[PrepareRenameResult, None]
    ) -> None:
        """Validate prepareRename result and prompt user for new name."""

        if not result or not self.document_rename_target:
            sublime.status_message("LSP: Cannot rename here")
            return

        # result can be a range or an object with range and placeholder
        try:
            if isinstance(result, dict):
                # PrepareRenameResult may include 'range' and optional 'placeholder'
                symbol_range = result.get("range")
                placeholder = result.get("placeholder")
            else:
                # Some servers return a simple range-like structure
                symbol_range = result
                placeholder = None

            if not symbol_range:
                sublime.status_message("LSP: Rename not available at this location")
                return

            self._prompt_rename(self.document_rename_target, symbol_range, placeholder)
        except Exception as e:
            print(f"[LSP Rename] Error handling prepareRename result: {e}")

    def _prompt_rename(
        self, document: object, symbol_range: dict, placeholder: Optional[str]
    ) -> None:
        """Show input panel prefilled with the symbol to rename."""
        view = document.view
        try:
            start = LineCharacter(**symbol_range["start"])
            end = LineCharacter(**symbol_range["end"])
            start_point = view.text_point(start.line, start.character)
            end_point = view.text_point(end.line, end.character)
        except Exception as e:
            print(f"[LSP Rename] Invalid range in prepareRename: {e}")
            return

        region = sublime.Region(start_point, end_point)
        old_name = view.substr(region) or (placeholder or "")
        row, col = view.rowcol(start_point)

        def request_rename(new_name: str) -> None:
            if not new_name:
                sublime.status_message("LSP: Rename cancelled")
                return
            if new_name == old_name:
                sublime.status_message("LSP: Name unchanged")
                return
            # perform rename on background thread
            self.textdocument_rename(view, row, col, new_name)

        view.window().show_input_panel(
            caption="Rename symbol",
            initial_text=old_name,
            on_done=request_rename,
            on_change=None,
            on_cancel=None,
        )

    @on_new_thread
    @require_server_capability("renameProvider")
    def textdocument_rename(
        self, view: sublime.View, row: int, col: int, new_name: str
    ) -> None:
        """Send rename request and apply resulting workspace edit."""

        # Save all open documents to ensure server has latest content
        for doc in self.session.get_documents():
            try:
                doc.view.run_command("save")
            except Exception:
                pass

        document = self.session.get_document(view)
        if not document:
            sublime.status_message("LSP: Document not available for rename")
            return

        self.document_rename_target = document
        sublime.status_message("LSP: Renaming symbol...")
        self.rename_request(
            {
                "newName": new_name,
                "position": {"line": row, "character": col},
                "textDocument": {"uri": path_to_uri(document.file_name)},
            }
        )

    @on_main_thread
    def handle_rename_result(
        self, context: Dict[str, Any], result: Union[LspWorkspaceEdit, None]
    ) -> None:
        """Apply workspace edit returned by the server and reset state."""
        if not result:
            sublime.status_message("LSP: No changes from rename")
            return

        try:
            apply_workspace_edit(self.session, result)
            sublime.status_message("LSP: Rename applied")
        except Exception as e:
            print(f"[LSP Rename] Error applying workspace edit: {e}")
            sublime.status_message("LSP: Rename failed")
