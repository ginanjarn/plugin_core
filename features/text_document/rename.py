from collections import namedtuple
from typing import Optional, Union, Dict, Any
import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from ..workspace_updater import apply_workspace_edit
from ...client_internal import BaseClient
from ...document import Document
from ...uri import path_to_uri
from ...lsprotocol.client import PrepareRenameResult, WorkspaceEdit as LspWorkspaceEdit
from ...utils import on_main_thread, on_new_thread

LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class DocumentRenameMixins(BaseClient):
    """Handle LSP prepareRename and rename requests with safer defaults and UX."""

    rename_target: Optional[Document] = None

    @on_new_thread
    def textdocument_preparerename(
        self, view: sublime.View, row: int, col: int
    ) -> None:
        """Ask server whether rename is allowed at the given position."""
        if not self.session.server_capabilities.get("renameProvider", False):
            sublime.status_message("LSP: Rename not supported by server")
            return

        document = self.session.get_document(view)
        if not document:
            return

        self.rename_target = document
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

        if not result or not self.rename_target:
            sublime.status_message("LSP: Cannot rename here")
            self.rename_target = None
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
                self.rename_target = None
                return

            self._prompt_rename(self.rename_target, symbol_range, placeholder)
        except Exception as e:
            print(f"[LSP Rename] Error handling prepareRename result: {e}")
            self.rename_target = None

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
            self.rename_target = None
            return

        region = sublime.Region(start_point, end_point)
        old_name = view.substr(region) or (placeholder or "")
        row, col = view.rowcol(start_point)

        def request_rename(new_name: str) -> None:
            if not new_name:
                sublime.status_message("LSP: Rename cancelled")
                self.rename_target = None
                return
            if new_name == old_name:
                sublime.status_message("LSP: Name unchanged")
                self.rename_target = None
                return
            # perform rename on background thread
            self.textdocument_rename(view, row, col, new_name)

        view.window().show_input_panel(
            caption="Rename symbol",
            initial_text=old_name,
            on_done=request_rename,
            on_change=None,
            on_cancel=lambda: setattr(self, "rename_target", None),
        )

    @on_new_thread
    def textdocument_rename(
        self, view: sublime.View, row: int, col: int, new_name: str
    ) -> None:
        """Send rename request and apply resulting workspace edit."""
        if not self.session.server_capabilities.get("renameProvider", False):
            sublime.status_message("LSP: Rename not supported by server")
            return

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

        self.rename_target = document
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
            self.rename_target = None
            return

        try:
            apply_workspace_edit(self.session, result)
            sublime.status_message("LSP: Rename applied")
        except Exception as e:
            print(f"[LSP Rename] Error applying workspace edit: {e}")
            sublime.status_message("LSP: Rename failed")
        finally:
            self.rename_target = None


class _PrepareRenameCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentRenameMixins

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        try:
            point = event.get("text_point") if isinstance(event, dict) else None
        except Exception:
            point = None

        if point is None:
            point = self.view.sel()[0].begin()

        row, column = self.view.rowcol(point)
        self.client.textdocument_preparerename(self.view, row, column)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)

    def want_event(self) -> bool:
        return True


class _RenameCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentRenameMixins

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit, row: int, column: int, new_name: str) -> None:
        self.client.textdocument_rename(self.view, row, column, new_name)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)
