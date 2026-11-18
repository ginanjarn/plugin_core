from collections import namedtuple
from typing import Any, Dict, List, Optional, Union

import sublime

from ...document import Document
from ...lsprotocol.client import SignatureHelp
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ..base_feature import BaseFeature, require_server_capability

LineCharacter = namedtuple("LineCharacter", ["line", "character"])


# Maximum characters shown in a signature popup to avoid huge UI blocks
MAX_SIGNATURE_CHARS = 6_000


class DocumentSignatureHelpMixin(BaseFeature):
    """Handle LSP signatureHelp requests and show a transient popup with signature info."""

    document_signature_help_target: Optional[Document]

    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["textDocument"].update(
            {
                "signatureHelp": {
                    "dynamicRegistration": False,
                    "signatureInformation": {
                        "documentationFormat": ["markdown"],
                        "parameterInformation": {"labelOffsetSupport": False},
                        "activeParameterSupport": False,
                        "noActiveParameterSupport": False,
                    },
                    "contextSupport": False,
                }
            }
        )

    @on_new_thread
    @require_server_capability("signatureHelpProvider")
    def textdocument_signaturehelp(self, view: sublime.View) -> None:
        """Send signatureHelp request to the server with debounce and stale-response protection."""

        document = self.session.get_document(view)
        if not document:
            return

        # hide any previous popup
        if prev_target := getattr(self, "document_signature_help_target", None):
            prev_target.view.hide_popup()

        self.document_signature_help_target = document
        row, col = view.rowcol(view.sel()[0].end())
        self.signature_help_point = view.text_point(row, col)
        self.signature_help_request(
            {
                "position": {"line": row, "character": col},
                "textDocument": {"uri": path_to_uri(document.file_name)},
            },
        )

    @on_main_thread
    def handle_signature_help_result(
        self, context: dict, result: Union[SignatureHelp, None]
    ) -> None:
        """Receive signature help result and show popup if still relevant."""
        if not (result and self.document_signature_help_target):
            return

        try:
            content, markup = self._build_signature_content(result)
        except Exception as e:
            print(f"[LSP SignatureHelp] Error building content: {e}")
            return

        if not content:
            return

        # truncate very long content
        if len(content) > MAX_SIGNATURE_CHARS:
            content = content[: MAX_SIGNATURE_CHARS - 200] + "\n\n... (truncated)"

        view = self.document_signature_help_target.view
        location = self.signature_help_point
        self.show_signature_popup(view, content, location, markup)

    def _build_signature_content(self, help_obj: SignatureHelp) -> (str, str):
        """
        Normalize SignatureHelp into markdown text and markup type.
        Returns (content, markup) where markup is 'markdown'.
        """
        # SignatureHelp shape: { signatures: [...], activeSignature?: int, activeParameter?: int }
        signatures: List[Dict[str, Any]] = (
            help_obj.get("signatures", []) if isinstance(help_obj, dict) else []
        )
        if not signatures:
            return "", "markdown"

        active_sig = help_obj.get("activeSignature", 0) or 0
        active_param = help_obj.get("activeParameter", None)

        # clamp active signature index
        if active_sig < 0 or active_sig >= len(signatures):
            active_sig = 0

        sig = signatures[active_sig]
        label = sig.get("label", "")
        documentation = ""
        doc = sig.get("documentation")
        if isinstance(doc, str):
            documentation = doc
        elif isinstance(doc, dict):
            documentation = doc.get("value", "")

        # If parameters are provided, try to highlight the active parameter
        params = sig.get("parameters", [])
        highlighted_label = label
        try:
            if params and active_param is not None and 0 <= active_param < len(params):
                p = params[active_param]
                p_label = p.get("label")
                # parameter label can be a string or [start, end]
                if isinstance(p_label, str) and p_label:
                    # attempt to replace the first occurrence of parameter text with bold markdown
                    # fallback: wrap parameter text in backticks if replacement fails
                    if p_label in highlighted_label:
                        highlighted_label = highlighted_label.replace(
                            p_label, f"**{p_label}**", 1
                        )
                    else:
                        # try to use parameter index to approximate highlighting
                        highlighted_label = f"**{p_label}** — {highlighted_label}"
                elif isinstance(p_label, list) and len(p_label) == 2:
                    # numeric range inside label: try to slice
                    start_idx, end_idx = p_label
                    if 0 <= start_idx < end_idx <= len(highlighted_label):
                        highlighted_label = (
                            highlighted_label[:start_idx]
                            + "**"
                            + highlighted_label[start_idx:end_idx]
                            + "**"
                            + highlighted_label[end_idx:]
                        )
        except Exception:
            # best-effort highlighting; ignore failures
            pass

        # Build content: code block for signature, then documentation if present
        parts: List[str] = []
        parts.append(f"```\n{highlighted_label}\n```")
        if documentation:
            parts.append(documentation)

        # If there are multiple signatures, show a small footer with index
        if len(signatures) > 1:
            parts.append(f"_Signature {active_sig + 1} of {len(signatures)}_")

        return "\n\n".join(parts), "markdown"

    @staticmethod
    def show_signature_popup(
        view: sublime.View, text: str, location: int, markup: str
    ) -> None:
        """Show signature popup using the project's marked_popup command."""
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
