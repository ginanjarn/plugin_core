from collections import namedtuple
from functools import wraps
from typing import List, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...uri import path_to_uri, uri_to_path
from ...lsprotocol.client import Client, SymbolInformation, DocumentSymbol


PathEncodedStr = str
LineCharacter = namedtuple("LineCharacter", ["line", "character"])
SymbolLocation = namedtuple("SymbolLocation", ["file_name", "row", "column"])
Symbol = namedtuple("Symbol", ["name", "location"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentSymbolMixins(Client):

    symbol_target = None

    @must_initialized
    def textdocument_symbol(self, view: sublime.View):
        if not self.session.server_capabilities.get("documentSymbolProvider", False):
            return
        if document := self.session.get_document(view):
            self.symbol_target = document
            self.document_symbol_request(
                {"textDocument": {"uri": path_to_uri(document.file_name)}}
            )

    def handle_document_symbol_result(
        self,
        context: dict,
        result: Union[List[SymbolInformation], List[DocumentSymbol], None],
    ) -> None:
        if not result:
            return

        view = self.symbol_target.view
        symbols = [self._get_symbol(view, s) for s in result]
        SymbolSelector(view, symbols).show_panel()

    def _get_symbol(
        self, view: sublime.View, symbol: Union[SymbolInformation, DocumentSymbol]
    ) -> Symbol:
        if location := symbol.get("location"):
            file_name = uri_to_path(location["uri"])
            start = LineCharacter(**location["range"]["start"])
            end = LineCharacter(**location["range"]["end"])
            region = sublime.Region(view.text_point(*start), view.text_point(*end))
            name = view.substr(region)
        else:
            file_name = view.file_name()
            start = LineCharacter(**symbol["range"]["start"])
            end = LineCharacter(**symbol["range"]["end"])
            name = symbol["name"]

        return Symbol(name, SymbolLocation(file_name, start[0], start[1]))


class SymbolSelector:

    def __init__(self, view: sublime.View, symbols: List[Symbol]):
        self.active_view = view
        self.active_window = view.window()

        self.visible_region = view.visible_region()
        self.active_selections = list(view.sel())

        self.symbols = symbols
        self._symbol_names = [s.name for s in symbols]

    def show_panel(self):
        self.active_window.show_quick_panel(
            items=self._symbol_names,
            on_select=self.on_select,
            flags=sublime.MONOSPACE_FONT,
            on_highlight=self.on_highlight,
            placeholder="Symbols",
        )

    def open_file(self, location: SymbolLocation, preview: bool = False):
        """open document"""

        file_name = f"{location.file_name}:{location.row+1}:{location.column+1}"
        flags = sublime.ENCODED_POSITION
        if preview:
            flags |= sublime.TRANSIENT

        self.active_window.open_file(file_name, flags=flags)

    def on_select(self, index: int):
        if index < 0:
            self.on_cancel()
        else:
            self.open_file(self.symbols[index].location)

    def on_highlight(self, index: int):
        self.open_file(self.symbols[index].location, preview=True)

    def on_cancel(self):
        self.active_window.focus_view(self.active_view)
        self.active_view.sel().clear()
        self.active_view.sel().add_all(self.active_selections)
        self.active_view.show(self.visible_region)


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _DocumentSymbolCommand(sublime_plugin.TextCommand):
    client: DocumentSymbolMixins = None

    @client_must_ready
    def run(self, edit: sublime.Edit):
        if not is_valid_document(self.view):
            return
        self.client.textdocument_symbol(self.view)

    def is_visible(self):
        return is_valid_document(self.view)
