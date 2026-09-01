import sublime

from .definition_mixin import DocumentDefinitionMixin


class _DocumentDefinitionCommandMixin:
    """Command to trigger 'Go to Definition'."""

    client: DocumentDefinitionMixin

    def run(self, edit: sublime.Edit) -> None:
        point = self.view.sel()[0].begin()
        row, column = self.view.rowcol(point)
        self.client.textdocument_definition(self.view, row, column)
