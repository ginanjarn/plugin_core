from collections import namedtuple

import sublime
from sublime import View

from ...client_internal import BaseClient
from ...uri import uri_to_path
from ...diagnostic_reporter import Diagnostic
from ...lsprotocol.client import PublishDiagnosticsParams
from ...utils import on_main_thread

LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class DocumentDiagnosticsMixins(BaseClient):

    @on_main_thread
    def handle_publish_diagnostics_notification(
        self, context: dict, params: PublishDiagnosticsParams
    ) -> None:
        file_name = uri_to_path(params["uri"])
        diagnostics = params["diagnostics"]

        documents = self.session.get_documents(lambda doc: doc.file_name == file_name)
        for document in documents:
            document.diagnostics = diagnostics
            items = [self.from_rpc(document.view, d) for d in diagnostics]
            self.session.diagnostic_reporter.report(document.view, items)

    def from_rpc(self, view: View, diagnostic: dict, /) -> Diagnostic:
        """"""
        start = LineCharacter(**diagnostic["range"]["start"])
        end = LineCharacter(**diagnostic["range"]["end"])
        region = sublime.Region(view.text_point(*start), view.text_point(*end))
        message = diagnostic["message"]
        if source := diagnostic.get("source"):
            message = f"{message} ({source})"
        # resolve highlight region if start == end
        if region.empty():
            region.b += 1

        return Diagnostic(diagnostic["severity"], region, message)
