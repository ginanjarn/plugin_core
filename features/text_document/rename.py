from typing import Optional

import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from .rename_mixin import DocumentRenameMixin


class _PrepareRenameCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentRenameMixin

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
    client: DocumentRenameMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit, row: int, column: int, new_name: str) -> None:
        self.client.textdocument_rename(self.view, row, column, new_name)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)
