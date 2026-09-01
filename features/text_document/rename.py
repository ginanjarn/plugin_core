import sublime

from .rename_mixin import DocumentRenameMixin


class _DocumentPrepareRenameCommandMixin:
    client: DocumentRenameMixin

    def run(self, edit: sublime.Edit) -> None:
        point = self.view.sel()[0].begin()
        row, column = self.view.rowcol(point)
        self.client.textdocument_preparerename(self.view, row, column)


class _DocumentRenameCommandMixin:
    client: DocumentRenameMixin

    def run(self, edit: sublime.Edit, row: int, column: int, new_name: str) -> None:
        self.client.textdocument_rename(self.view, row, column, new_name)
