from typing import Optional

import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from .definition_mixin import DocumentDefinitionMixin


class _GotoDefinitionCommand(PluginBase, sublime_plugin.TextCommand):
    """Command to trigger 'Go to Definition'."""

    client: DocumentDefinitionMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit, event: Optional[dict] = None) -> None:
        try:
            point = event.get("text_point")
        except Exception:
            point = self.view.sel()[0].begin()

        row, column = self.view.rowcol(point)
        self.client.textdocument_definition(self.view, row, column)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)

    def want_event(self) -> bool:
        return True
