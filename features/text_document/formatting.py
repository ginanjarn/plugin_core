import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from .formatting_mixin import DocumentFormattingMixin


class _DocumentFormattingCommand(PluginBase, sublime_plugin.TextCommand):
    """Command to trigger document formatting."""

    client: DocumentFormattingMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit) -> None:
        self.client.textdocument_formatting(self.view)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)
