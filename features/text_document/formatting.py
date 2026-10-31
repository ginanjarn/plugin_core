import sublime

from .formatting_mixin import DocumentFormattingMixin


class _DocumentFormattingCommandMixin:
    """Command to trigger document formatting."""

    client: DocumentFormattingMixin

    def document_formatting(self, edit: sublime.Edit) -> None:
        self.client.textdocument_formatting(self.view)
