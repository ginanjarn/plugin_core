import threading
from collections import namedtuple
from functools import wraps
from html import escape as escape_html
import sublime
import sublime_plugin

from ...document import Document, is_valid_document
from ...message import Result
from ...session import Session
from ...uri import path_to_uri


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class HoverEventListener(sublime_plugin.EventListener):
    client = None

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


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentHoverMixins:

    hover_target = None

    @must_initialized
    def textdocument_hover(self, view: sublime.View, row: int, col: int):
        # method = "textDocument/hover"
        # In multi row/column layout, new popup will created in current View,
        # but active popup doesn't discarded.
        if other := self.hover_target:
            other.view.hide_popup()

        if document := self.session.get_document(view):
            if message := self._get_diagnostic_message(document, row, col):
                self.show_popup(view, message, row, col)
                return

            self.hover_target = document
            self.request_textdocument_hover(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                }
            )

    def request_textdocument_hover(self, params: dict):
        self.send_request("textDocument/hover", params)

    def handle_textdocument_hover(self, session: Session, result: Result):
        if not result:
            return
        message = result["contents"]["value"]
        row, col = LineCharacter(**result["range"]["start"])
        self.show_popup(self.hover_target.view, message, row, col)

    @staticmethod
    def show_popup(
        view: sublime.View,
        text: str,
        row: int,
        col: int,
        keep_visible: bool = False,
    ):
        point = view.text_point(row, col)
        view.run_command(
            "marked_popup",
            {
                "location": point,
                "text": text,
                "markup": "markdown",
                "keep_visible": keep_visible,
            },
        )

    def _get_diagnostic_message(self, document: Document, row: int, col: int):
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
