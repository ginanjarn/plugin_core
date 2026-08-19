from collections import namedtuple
from html import escape as escape_html
from typing import Union, Optional, List
import sublime
import sublime_plugin

from ..plugin_base import PluginBase, client_must_ready, must_valid_document
from ...client_internal import BaseClient
from ...document import Document
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import Hover

LineCharacter = namedtuple("LineCharacter", ["line", "character"])

# Maximum characters shown in a hover popup to avoid huge UI blocks
MAX_HOVER_CHARS = 12_000


class DocumentHoverMixins(BaseClient):
    """Handle LSP hover requests and show popups with diagnostics + hover content."""

    hover_target: Optional[Document] = None
    hover_point: int = 0
    diagnostic_message: str = ""

    @on_new_thread
    def textdocument_hover(self, view: sublime.View, row: int, col: int) -> None:
        """Send hover request to the server. Cancel/replace any pending hover."""
        if not self.session.server_capabilities.get("hoverProvider", False):
            return

        # Hide previous popup if any
        if self.hover_target:
            try:
                self.hover_target.view.hide_popup()
            except Exception:
                pass

        document = self.session.get_document(view)
        if not document:
            return

        self.hover_point = view.text_point(row, col)
        self.diagnostic_message = self._get_diagnostic_message(document, row, col)
        if self.diagnostic_message:
            # show diagnostics immediately (markdown)
            self.show_hover_popup(
                view, self.diagnostic_message, self.hover_point, "markdown"
            )

        self.hover_target = document
        # send request; include request_id in context so handler can check it
        self.hover_request(
            {
                "position": {"character": col, "line": row},
                "textDocument": {"uri": path_to_uri(document.file_name)},
            },
        )

    @on_main_thread
    def handle_hover_result(self, context: dict, result: Union[Hover, None]) -> None:
        """Receive hover result and show popup if still relevant."""
        if not result:
            return

        if not self.hover_target:
            return

        try:
            text, markup = self._get_hover_content(result)
        except Exception as e:
            print(f"[LSP Hover] Error parsing hover content: {e}")
            return

        contents: List[str] = []
        if self.diagnostic_message:
            contents.append(self.diagnostic_message)

        if text:
            # truncate very long hover content
            if len(text) > MAX_HOVER_CHARS:
                text = text[: MAX_HOVER_CHARS - 200] + "\n\n... (truncated)"
            contents.append(text)

        if not contents:
            return

        hr_line = "\n***\n"
        combined = hr_line.join(contents)
        self.show_hover_popup(
            self.hover_target.view, combined, self.hover_point, markup
        )

    def _get_hover_content(self, hover: Hover) -> tuple:
        """
        Normalize hover contents into (text, markup).
        Accepts:
          - MarkupContent: {"kind": "markdown"|"plaintext", "value": "..."}
          - string
          - MarkedString or list of MarkedString
        Returns (content, markup) where markup is "markdown" or "plain".
        """
        markup = "markdown"
        contents = hover.get("contents") if isinstance(hover, dict) else None

        if contents is None:
            return "", markup

        # MarkupContent
        if isinstance(contents, dict):
            value = contents.get("value", "")
            kind = contents.get("kind", "").lower()
            if kind == "plaintext":
                return escape_html(value), "plain"
            return value, "markdown"

        # Plain string
        if isinstance(contents, str):
            # treat as markdown but escape to be safe if it looks like plain text
            return escape_html(contents), "plain"

        # List of items
        if isinstance(contents, list):
            parts: List[str] = []
            # each item can be string or dict
            for item in contents:
                if isinstance(item, str):
                    parts.append(escape_html(item))
                elif isinstance(item, dict):
                    # MarkupContent inside list
                    val = item.get("value", "")
                    kind = item.get("kind", "").lower()
                    if kind == "plaintext":
                        parts.append(escape_html(val))
                    else:
                        parts.append(val)
                else:
                    # unknown item type, stringify safely
                    parts.append(escape_html(str(item)))
            # If any part looks like markdown (contains backticks or markdown headings), prefer markdown
            joined = "\n\n".join(parts)
            prefer_md = any(("#" in p or "`" in p or "```" in p) for p in parts)
            return (joined, "markdown" if prefer_md else "plain")

        # Fallback
        return escape_html(str(contents)), "plain"

    @staticmethod
    def show_hover_popup(
        view: sublime.View, text: str, location: int, markup: str
    ) -> None:
        """
        Show popup using the project's marked_popup command.
        - markup: "markdown" or "plain"
        """
        # Ensure text is not None
        if text is None:
            return
        view.run_command(
            "marked_popup",
            {
                "location": location,
                "text": text,
                "markup": markup,
            },
        )

    @staticmethod
    def _get_diagnostic_message(document: Document, row: int, col: int) -> str:
        """
        Build a small markdown list of diagnostics that cover the hovered position.
        Returns an empty string if none.
        """
        LC = LineCharacter
        try:
            items = [
                d
                for d in getattr(document, "diagnostics", [])
                if LC(**d["range"]["start"]) <= LC(row, col) <= LC(**d["range"]["end"])
            ]
        except Exception:
            items = []

        if not items:
            return ""

        def build_message(d: dict) -> str:
            code = d.get("code")
            msg = d.get("message", "")
            if code:
                return f"{escape_html(str(code))} — {escape_html(msg)}"
            return escape_html(msg)

        lines = [f"- {build_message(d)}" for d in items]
        return "\n".join(lines)


class HoverEventListener(PluginBase, sublime_plugin.ViewEventListener):
    client: DocumentHoverMixins

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
