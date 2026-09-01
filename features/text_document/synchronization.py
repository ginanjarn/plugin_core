from typing import List

import sublime

from ...document import TextChange
from .synchronization_mixin import DocumentSynchronizerMixin


class SynchronizeEventAdapter:
    client: DocumentSynchronizerMixin

    def didopen(self, view: sublime.View, *, reload: bool = False) -> None:
        self.client.textdocument_didopen(view, reload=reload)

    def didsave(self, view: sublime.View) -> None:
        self.client.textdocument_didsave(view)

    def didclose(self, view: sublime.View) -> None:
        self.client.textdocument_didclose(view)

    def didchange(self, view: sublime.View, changes: List[TextChange]) -> None:
        self.client.textdocument_didchange(view, changes)


class DocumentSynchronizeEventMixin(SynchronizeEventAdapter):

    def on_activated_async(self) -> None:
        try:
            self.didopen(self.view)
        except Exception:
            print("[LSP Sync] on_activated_async error")

    def on_load_async(self) -> None:
        try:
            self.didopen(self.view, reload=True)
        except Exception:
            print("[LSP Sync] on_load_async error")

    def on_reload_async(self) -> None:
        try:
            self.didopen(self.view, reload=True)
        except Exception:
            print("[LSP Sync] on_reload_async error")

    def on_revert_async(self) -> None:
        try:
            self.didopen(self.view, reload=True)
        except Exception:
            print("[LSP Sync] on_revert_async error")

    def on_post_save_async(self) -> None:
        try:
            self.didsave(self.view)
        except Exception:
            print("[LSP Sync] on_post_save_async error")

    def on_close(self) -> None:
        try:
            self.didclose(self.view)
        except Exception:
            print("[LSP Sync] on_close error")


class DocumentChangeEventMixin(SynchronizeEventAdapter):
    def on_text_changed(self, changes: List[sublime.TextChange]) -> None:
        try:
            view = self.buffer.primary_view()
            # Convert Sublime TextChange to our TextChange dataclass safely
            converted = []
            for c in changes:
                try:
                    start = (c.a.row, c.a.col)
                    end = (c.b.row, c.b.col)
                    converted.append(TextChange(start, end, c.str, c.len_utf8))
                except Exception:
                    # skip malformed change entries
                    continue
            if converted:
                self.didchange(view, converted)
        except Exception:
            print("[LSP Sync] on_text_changed error")
