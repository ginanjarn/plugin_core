from typing import List

import sublime

from ..document import TextChange
from .synchronization_mixin import DocumentSynchronizerMixin


class DocumentSynchronizeEventMixin:
    client: DocumentSynchronizerMixin

    def document_didopen(self) -> None:
        self.client.textdocument_didopen(self.view)

    def document_didopen_reload(self) -> None:
        self.client.textdocument_didopen(self.view, reload=True)

    def document_didsave(self) -> None:
        self.client.textdocument_didsave(self.view)

    def document_didclose(self) -> None:
        self.client.textdocument_didclose(self.view)


class DocumentChangeEventMixin:
    client: DocumentSynchronizerMixin

    def document_didchange(self, changes: List[sublime.TextChange]) -> None:
        view = self.buffer.primary_view()

        # Convert Sublime TextChange to our TextChange dataclass safely
        converted = [self.convert_text_change(c) for c in changes]
        self.client.textdocument_didchange(view, converted)

    def convert_text_change(self, c: sublime.TextChange):
        start = (c.a.row, c.a.col)
        end = (c.b.row, c.b.col)
        variable1 = TextChange(start, end, c.str, c.len_utf8)
        return variable1
