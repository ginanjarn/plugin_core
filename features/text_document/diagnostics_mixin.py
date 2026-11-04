from collections import namedtuple

import sublime
from sublime import View

from ...base_client import BaseClient
from ...lsprotocol.client import PublishDiagnosticsParams
from ...uri import uri_to_path
from ...utils import on_main_thread
from .diagnostic_reporter import Diagnostic

LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class DocumentDiagnosticsMixin(BaseClient):
    """Handles diagnostics notifications from the language server."""

    def set_client_capabilities(self):
        self.session.client_capabilities["textDocument"].update(
            {
                "diagnostic": {
                    "relatedInformation": False,
                    "tagSupport": {"valueSet": [1, 2]},
                    "codeDescriptionSupport": False,
                    "dataSupport": False,
                    "dynamicRegistration": False,
                    "relatedDocumentSupport": False,
                },
                "publishDiagnostics": {
                    "relatedInformation": False,
                    "tagSupport": {"valueSet": [1, 2]},
                    "codeDescriptionSupport": False,
                    "dataSupport": False,
                    "versionSupport": False,
                },
            }
        )

    @on_main_thread
    def handle_publish_diagnostics_notification(
        self, context: dict, params: PublishDiagnosticsParams
    ) -> None:
        file_name = uri_to_path(params["uri"])
        diagnostics = params.get("diagnostics", [])

        documents = self.session.get_documents(lambda doc: doc.file_name == file_name)
        for document in documents:
            document.diagnostics = diagnostics
            items = [self.from_rpc(document.view, d) for d in diagnostics]
            self.session.diagnostic_reporter.report(document.view, items)

    def from_rpc(self, view: View, diagnostic: dict, /) -> Diagnostic:
        """Convert LSP diagnostic dict into a Diagnostic object."""
        try:
            start = LineCharacter(**diagnostic["range"]["start"])
            end = LineCharacter(**diagnostic["range"]["end"])
            region = sublime.Region(view.text_point(*start), view.text_point(*end))
        except Exception as e:
            print(f"[LSP Diagnostics] Invalid range: {e}")
            region = sublime.Region(0, 1)

        # Build message with optional source, code, and tags
        message = diagnostic.get("message", "")
        if source := diagnostic.get("source"):
            message += f" ({source})"
        if code := diagnostic.get("code"):
            message += f" [code: {code}]"
        if tags := diagnostic.get("tags"):
            message += f" [tags: {', '.join(map(str, tags))}]"

        # Ensure region is visible even if empty
        if region.empty():
            region.b += 1

        severity = diagnostic.get("severity", 2)  # default to 'warning' if missing
        return Diagnostic(severity, region, message)
