from collections import namedtuple
from typing import Optional, List, Union

import sublime

from ...client_internal import BaseClient
from ...uri import path_to_uri, uri_to_path
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import Definition, Location, DefinitionLink

PathEncodedStr = str
LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class DocumentDefinitionMixin(BaseClient):
    """Handles LSP definition requests and results."""

    definition_target: Optional[object] = None

    @on_new_thread
    def textdocument_definition(self, view: sublime.View, row: int, col: int) -> None:
        if not self.session.server_capabilities.get("definitionProvider"):
            return
        document = self.session.get_document(view)
        if document:
            self.definition_target = document
            self.definition_request(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                }
            )

    @on_main_thread
    def handle_definition_result(
        self, context: dict, result: Union[Definition, List[DefinitionLink], None]
    ) -> None:
        if not result or not self.definition_target:
            return

        view = self.definition_target.view
        self.definition_target = None  # reset after use

        if isinstance(result, list):
            locations = [self._build_location(l) for l in result]
        else:
            locations = [self._build_location(result)]

        LocationSelector(view, locations).show_panel()

    @staticmethod
    def _build_location(location: Union[Location, DefinitionLink]) -> PathEncodedStr:
        try:
            uri = location.get("uri") or location.get("targetUri")
            range_start = location.get("range", {}).get("start") or location.get(
                "targetRange", {}
            ).get("start")
            if not uri or not range_start:
                return "<invalid-location>"
            file_name = uri_to_path(uri)
            start_row, start_col = LineCharacter(**range_start)
            return f"{file_name}:{start_row+1}:{start_col+1}"
        except Exception as e:
            print(f"[LSP Definition] Error parsing location: {e}")
            return "<invalid-location>"


class LocationSelector:
    """Handles quick panel selection and file opening."""

    def __init__(self, current_view: sublime.View, locations: List[PathEncodedStr]):
        self.current_view = current_view
        self.window = current_view.window()
        self._visible_region = current_view.visible_region()
        self._selections = list(current_view.sel())
        self._locations = locations
        self._previewed_view = None

    def show_panel(self) -> None:
        items = [(loc, "Definition") for loc in self._locations]
        self.window.show_quick_panel(
            items=items,
            on_select=self.on_select,
            flags=sublime.MONOSPACE_FONT,
            on_highlight=self.on_highlight,
            placeholder="Go to definition...",
        )

    def open_file(self, file_name: PathEncodedStr, preview: bool = False) -> None:
        flags = sublime.ENCODED_POSITION
        if preview:
            flags |= sublime.TRANSIENT
        self._previewed_view = self.window.open_file(file_name, flags=flags)

    def on_select(self, index: int) -> None:
        if index < 0:
            self.on_cancel()
        else:
            self.open_file(self._locations[index])

    def on_highlight(self, index: int) -> None:
        self.open_file(self._locations[index], preview=True)

    def on_cancel(self) -> None:
        self.window.focus_view(self.current_view)
        self.current_view.sel().clear()
        self.current_view.sel().add_all(self._selections)
        self.current_view.show(self._visible_region)
