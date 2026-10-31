import sublime

from .symbol_mixin import DocumentSymbolMixin


class _DocumentSymbolCommandMixin:
    client: DocumentSymbolMixin

    def document_symbol(self, edit: sublime.Edit) -> None:
        self.client.textdocument_symbol(self.view)
