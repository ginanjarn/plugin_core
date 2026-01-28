import threading
from collections import namedtuple
from functools import wraps
from html import escape as escape_html
from typing import Union
import sublime
import sublime_plugin

from ...document import Document, is_valid_document
from ...uri import path_to_uri
from ...lsprotocol.client import Client, Hover


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentHoverMixins(Client):

    hover_target = None
    hover_point = 0
    diagnostic_message = ""

    @must_initialized
    def textdocument_hover(self, view: sublime.View, row: int, col: int):
        if not self.session.server_capabilities.get("hoverProvider", False):
            return
        # method = "textDocument/hover"
        # In multi row/column layout, new popup will created in current View,
        # but active popup doesn't discarded.
        if other := self.hover_target:
            other.view.hide_popup()

        if document := self.session.get_document(view):
            self.hover_point = view.text_point(row, col)

            diagnostic_message = self._get_diagnostic_message(document, row, col)
            self.diagnostic_message = diagnostic_message
            if diagnostic_message:
                self.show_popup(view, diagnostic_message, self.hover_point, "markdown")

            self.hover_target = document
            self.hover_request(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                }
            )

    def handle_hover_result(self, context: dict, result: Union[Hover, None]) -> None:
        if not result:
            return

        text, markup = self._get_hover_content(result)
        popup_content = "\n***\n".join([self.diagnostic_message, text])
        self.show_popup(self.hover_target.view, popup_content, self.hover_point, markup)

    def _get_hover_content(self, hover: Hover) -> tuple:
        markup = "plaintext"
        contents = hover["contents"]

        if isinstance(contents, dict):
            value = contents["value"]
            markup = contents.get("kind", "plaintext")
        elif isinstance(contents, str):
            value = contents

        elif isinstance(contents, list):
            values = []
            for c in contents:
                if isinstance(c, str):
                    values.append(c)
                if isinstance(contents[0], dict):
                    values.append(c["value"])
            value = "\n".join(values)

        return value, markup

    @staticmethod
    def show_popup(view: sublime.View, text: str, location: int, markup: str):
        view.run_command(
            "marked_popup",
            {
                "location": location,
                "text": text,
                "markup": markup,
            },
        )

    @staticmethod
    def _get_diagnostic_message(document: Document, row: int, col: int):
        items = [
            d["message"]
            for d in document.diagnostics
            if LineCharacter(**d["range"]["start"])
            <= LineCharacter(row, col)
            <= LineCharacter(**d["range"]["end"])
        ]
        if not items:
            return ""

        title = "### Diagnostics:\n"
        diagnostic_message = "\n".join([f"- {escape_html(d)}" for d in items])
        return f"{title}\n{diagnostic_message}"


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class HoverEventListener(sublime_plugin.EventListener):
    client: DocumentHoverMixins = None

    @client_must_ready
    def on_hover(self, view: sublime.View, point: int, hover_zone: sublime.HoverZone):
        if hover_zone != sublime.HoverZone.TEXT:
            return
        if not is_valid_document(view):
            return
        row, col = view.rowcol(point)
        threading.Thread(target=self._on_hover_task, args=(view, row, col)).start()

    def _on_hover_task(self, view: sublime.View, row: int, col: int):
        # Hover may be not in current active document, open it
        self.client.textdocument_didopen(view)
        self.client.textdocument_hover(view, row, col)
