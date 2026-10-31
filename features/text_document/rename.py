import sublime

from .rename_mixin import DocumentRenameMixin


class _DocumentPrepareRenameCommandMixin:
    client: DocumentRenameMixin

    def document_prepare_rename(self, edit: sublime.Edit) -> None:
        self.client.textdocument_preparerename(self.view)


class _DocumentRenameCommandMixin:
    client: DocumentRenameMixin

    def document_rename(
        self, edit: sublime.Edit, row: int, column: int, new_name: str
    ) -> None:
        self.client.textdocument_rename(self.view, row, column, new_name)
