import sublime

from .definition_mixin import DocumentDefinitionMixin


class _DocumentDefinitionCommandMixin:
    """Command to trigger 'Go to Definition'."""

    client: DocumentDefinitionMixin

    def document_definition(self, edit: sublime.Edit) -> None:
        self.client.textdocument_definition(self.view)
