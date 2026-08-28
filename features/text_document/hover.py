import sublime
import sublime_plugin

from ..plugin_base import PluginBase, client_must_ready, must_valid_document
from .hover_mixin import DocumentHoverMixin


class HoverEventListener(PluginBase, sublime_plugin.ViewEventListener):
    client: DocumentHoverMixin

    @client_must_ready
    @must_valid_document
    def on_hover(self, point: int, hover_zone: sublime.HoverZone) -> None:
        if hover_zone != sublime.HoverZone.TEXT:
            return
        row, col = self.view.rowcol(point)
        self._on_hover_task(self.view, row, col)

    def _on_hover_task(self, view: sublime.View, row: int, col: int) -> None:
        # Ensure document is open in session and then request hover
        try:
            self.client.textdocument_didopen(view)
        except Exception:
            pass
        self.client.textdocument_hover(view, row, col)
