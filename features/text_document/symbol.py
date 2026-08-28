import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    must_valid_document,
    is_valid_document,
)
from .symbol_mixin import DocumentSymbolMixin


class _DocumentSymbolCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentSymbolMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit) -> None:
        self.client.textdocument_symbol(self.view)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)
