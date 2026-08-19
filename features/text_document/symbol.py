from collections import namedtuple
from typing import List, Union, Optional, Tuple, Dict, Any
import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    must_valid_document,
    is_valid_document,
)
from ...client_internal import BaseClient
from ...uri import path_to_uri, uri_to_path
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import SymbolInformation, DocumentSymbol

PathEncodedStr = str
LineCharacter = namedtuple("LineCharacter", ["line", "character"])
SymbolLocation = namedtuple("SymbolLocation", ["file_name", "row", "column"])
Symbol = namedtuple("Symbol", ["name", "kind", "location", "container_name"])


class DocumentSymbolMixins(BaseClient):
    """Request document symbols and present them in a quick panel with previews."""

    symbol_target: Optional[object] = None

    @on_new_thread
    def textdocument_symbol(self, view: sublime.View) -> None:
        """Request document symbols if supported by the server."""
        if not self.session.server_capabilities.get("documentSymbolProvider", False):
            return

        document = self.session.get_document(view)
        if not document:
            return

        self.symbol_target = document
        self.document_symbol_request(
            {"textDocument": {"uri": path_to_uri(document.file_name)}},
        )

    @on_main_thread
    def handle_document_symbol_result(
        self,
        context: Dict[str, Any],
        result: Union[List[SymbolInformation], List[DocumentSymbol], None],
    ) -> None:
        """Handle server response and show symbol selector if still relevant."""
        if not result or not self.symbol_target:
            return

        try:
            view = self.symbol_target.view
            symbols = self._flatten_symbols(view, result)
            if not symbols:
                sublime.status_message("LSP: No symbols found")
                self.symbol_target = None
                return

            selector = SymbolSelector(view, symbols)
            selector.show_panel()
        except Exception as e:
            print(f"[LSP DocumentSymbol] Error handling result: {e}")
        finally:
            self.symbol_target = None

    def _flatten_symbols(
        self,
        view: sublime.View,
        result: Union[List[SymbolInformation], List[DocumentSymbol]],
    ) -> List[Symbol]:
        """
        Convert SymbolInformation or hierarchical DocumentSymbol list into a flat list of Symbol tuples.
        Preserves container names for display.
        """
        symbols: List[Symbol] = []

        def add_symbol_from_info(
            info: Dict[str, Any], container: Optional[str] = None
        ) -> None:
            try:
                location = info.get("location")
                if location:
                    file_name = uri_to_path(location["uri"])
                    start = LineCharacter(**location["range"]["start"])
                else:
                    # fallback to current view file and range if present
                    file_name = view.file_name() or "<untitled>"
                    start = LineCharacter(**info["range"]["start"])
                name = info.get("name", "<unknown>")
                kind = info.get("kind", 0)
                symbols.append(
                    Symbol(
                        name,
                        kind,
                        SymbolLocation(file_name, start.line, start.character),
                        container,
                    )
                )
            except Exception as e:
                print(f"[LSP DocumentSymbol] Skipping malformed SymbolInformation: {e}")

        def add_document_symbol(
            ds: Dict[str, Any], container: Optional[str] = None
        ) -> None:
            try:
                name = ds.get("name", "<unknown>")
                kind = ds.get("kind", 0)
                range_start = ds.get("range", {}).get("start") or ds.get(
                    "selectionRange", {}
                ).get("start")
                if not range_start:
                    raise ValueError("missing range")
                file_name = view.file_name() or "<untitled>"
                start = LineCharacter(**range_start)
                symbols.append(
                    Symbol(
                        name,
                        kind,
                        SymbolLocation(file_name, start.line, start.character),
                        container,
                    )
                )
                # recurse into children if present
                for child in ds.get("children", []) or []:
                    add_document_symbol(child, container=name)
            except Exception as e:
                print(f"[LSP DocumentSymbol] Skipping malformed DocumentSymbol: {e}")

        # Determine whether result is SymbolInformation list or DocumentSymbol list
        if not isinstance(result, list):
            return symbols

        # Heuristic: SymbolInformation entries have 'location' key
        if result and isinstance(result[0], dict) and "location" in result[0]:
            for info in result:
                add_symbol_from_info(info)
        else:
            for ds in result:
                add_document_symbol(ds)

        return symbols


class SymbolSelector:
    """Quick panel UI for selecting and previewing symbols."""

    def __init__(self, view: sublime.View, symbols: List[Symbol]):
        self.view = view
        self.window = view.window()
        self.visible_region = view.visible_region()
        self.selections = list(view.sel())
        self.symbols = symbols
        # Build display items as (main, annotation)
        self.items: List[Tuple[str, str]] = []
        for s in symbols:
            # show container name as annotation when available
            container = f" — {s.container_name}" if s.container_name else ""
            kind_name = self._kind_name(s.kind)
            annotation = f"{kind_name}{container}"
            self.items.append((s.name, annotation))

        self._previewed_view = None

    def show_panel(self) -> None:
        # Sublime accepts list of strings or list of tuples (main, annotation)
        self.window.show_quick_panel(
            items=self.items,
            on_select=self.on_select,
            flags=sublime.MONOSPACE_FONT,
            on_highlight=self.on_highlight,
            placeholder="Symbols",
        )

    def _kind_name(self, kind: int) -> str:
        # Minimal mapping; extend as needed
        mapping = {
            1: "File",
            2: "Module",
            3: "Namespace",
            4: "Package",
            5: "Class",
            6: "Method",
            7: "Property",
            8: "Field",
            9: "Constructor",
            10: "Enum",
            11: "Interface",
            12: "Function",
            13: "Variable",
            14: "Constant",
            15: "String",
            16: "Number",
            17: "Boolean",
            18: "Array",
        }
        return mapping.get(kind, "Symbol")

    def open_file(self, location: SymbolLocation, preview: bool = False) -> None:
        """Open file at encoded position. Use TRANSIENT for preview to avoid creating many tabs."""
        file_pos = f"{location.file_name}:{location.row+1}:{location.column+1}"
        flags = sublime.ENCODED_POSITION
        if preview:
            flags |= sublime.TRANSIENT
        try:
            self._previewed_view = self.window.open_file(file_pos, flags=flags)
        except Exception as e:
            print(f"[LSP SymbolSelector] Failed to open {file_pos}: {e}")

    def on_select(self, index: int) -> None:
        if index < 0:
            self.on_cancel()
            return
        symbol = self.symbols[index]
        self.open_file(symbol.location, preview=False)

    def on_highlight(self, index: int) -> None:
        if index < 0 or index >= len(self.symbols):
            return
        symbol = self.symbols[index]
        self.open_file(symbol.location, preview=True)

    def on_cancel(self) -> None:
        try:
            self.window.focus_view(self.view)
            self.view.sel().clear()
            self.view.sel().add_all(self.selections)
            self.view.show(self.visible_region)
        except Exception:
            pass


class _DocumentSymbolCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentSymbolMixins

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit) -> None:
        self.client.textdocument_symbol(self.view)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)
