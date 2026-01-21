from collections import namedtuple
from functools import wraps
from typing import Optional, List, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...uri import path_to_uri, uri_to_path
from ...lsprotocol.client import Client, Definition, Location, DefinitionLink


PathEncodedStr = str
"""Path encoded '<file_name>:<row>:<column>'"""
LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentDefinitionMixins(Client):

    definition_target = None

    @must_initialized
    def textdocument_definition(self, view: sublime.View, row: int, col: int):
        if document := self.session.get_document(view):
            self.definition_target = document
            self.definition_request(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                },
            )

    def handle_definition_result(
        self, context: dict, result: Union[Definition, List[DefinitionLink], None]
    ) -> None:
        if not result:
            return
        view = self.definition_target.view
        if isinstance(result, list):
            locations = [self._build_location(l) for l in result]
        else:
            locations = [self._build_location(result)]

        LocationSelector(view, locations).show_panel()

    @staticmethod
    def _build_location(location: Union[Location, DefinitionLink]) -> PathEncodedStr:
        try:
            file_name = uri_to_path(location["uri"])
            start_row, start_col = LineCharacter(**location["range"]["start"])
        except KeyError:
            file_name = uri_to_path(location["targetUri"])
            start_row, start_col = LineCharacter(**location["targetRange"]["start"])

        return f"{file_name}:{start_row+1}:{start_col+1}"


class LocationSelector:

    def __init__(self, current_view: sublime.View, locations: List[PathEncodedStr]):
        self.current_view = current_view
        self.window = current_view.window()

        self._visible_region = current_view.visible_region()
        self._selections = list(current_view.sel())
        self._locations = locations

        self._opened_view = None

    def show_panel(self):
        self.window.show_quick_panel(
            items=self._locations,
            on_select=self.on_select,
            flags=sublime.MONOSPACE_FONT,
            on_highlight=self.on_highlight,
            placeholder="Open location...",
        )

    def open_file(self, file_name: PathEncodedStr, preview: bool = False):
        """open document"""
        flags = sublime.ENCODED_POSITION
        if preview:
            flags |= sublime.TRANSIENT

        self.window.open_file(file_name, flags=flags)

    def on_select(self, index: int):
        if index < 0:
            self.on_cancel()
        else:
            self.open_file(self._locations[index])

    def on_highlight(self, index: int):
        self.open_file(self._locations[index], preview=True)

    def on_cancel(self):
        self.window.focus_view(self.current_view)
        self.current_view.sel().clear()
        self.current_view.sel().add_all(self._selections)
        self.current_view.show(self._visible_region)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _GotoDefinitionCommand(sublime_plugin.TextCommand):
    client: DocumentDefinitionMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit, event: Optional[dict] = None):
        if not is_valid_document(self.view):
            return

        try:
            point = event["text_point"]
        except (AttributeError, KeyError):
            point = self.view.sel()[0].begin()

        row, column = self.view.rowcol(point)
        self.client.textdocument_definition(self.view, row, column)

    def is_visible(self):
        return is_valid_document(self.view)

    def want_event(self):
        return True
