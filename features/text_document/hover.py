import sublime

from .hover_mixin import DocumentHoverMixin


class DocumentHoverEventMixin:
    client: DocumentHoverMixin

    def on_hover(self, point: int, hover_zone: sublime.HoverZone) -> None:
        if hover_zone != sublime.HoverZone.TEXT:
            return

        # Pointer may hover on inactive view. Sync opened document to server.
        if self.view != sublime.active_window().active_view():
            self.client.textdocument_didopen(self.view)

        row, col = self.view.rowcol(point)
        self.client.textdocument_hover(self.view, row, col)
