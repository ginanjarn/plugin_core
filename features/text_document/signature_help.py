from typing import List, Optional

import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    must_valid_document,
    is_valid_document,
)
from .signature_help_mixin import DocumentSignatureHelpMixin


class _DocumentSignatureHelpCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentSignatureHelpMixin

    @client_must_ready
    def run(self, edit: sublime.Edit) -> None:
        if not is_valid_document(self.view):
            return
        point = self.view.sel()[0].begin()
        row, column = self.view.rowcol(point)
        self.client.textdocument_signaturehelp(self.view, row, column)


class DocumentSignatureHelpEventListener(PluginBase, sublime_plugin.ViewEventListener):
    """
    Trigger signature help on typing trigger characters and hide popup on cursor movement.
    Uses server-provided triggerCharacters when available.
    """

    client: DocumentSignatureHelpMixin
    _trigger_characters: Optional[List[str]] = None
    insert_commands = {"insert", "insert_snippet", "insert_completion"}

    @client_must_ready
    @must_valid_document
    def on_modified_async(self) -> None:
        # Only react to insert-like commands to avoid triggering on non-insert edits
        name, *_ = self.view.command_history(0)
        if name not in self.insert_commands:
            return

        # get the character just inserted
        sel = self.view.sel()
        if not sel:
            return
        point = sel[0].begin()
        if point == 0:
            return
        char = self.view.substr(point - 1)
        if char in self.trigger_characters:
            row, column = self.view.rowcol(point)
            self.client.textdocument_signaturehelp(self.view, row, column)

    @client_must_ready
    @must_valid_document
    def on_selection_modified_async(self) -> None:
        # hide popup when the selection moves away (user navigates)
        try:
            if self.view.is_popup_visible():
                self.view.hide_popup()
        except Exception:
            pass

    @property
    def trigger_characters(self) -> List[str]:
        if self._trigger_characters is not None:
            return self._trigger_characters

        try:
            capabilities = self.client.session.server_capabilities
            chars = capabilities.get("signatureHelpProvider", {}).get(
                "triggerCharacters", ["("]
            )
            # ensure list of single-character strings
            chars = [c for c in chars if isinstance(c, str) and c]
        except Exception:
            chars = ["("]

        self._trigger_characters = chars
        return self._trigger_characters
