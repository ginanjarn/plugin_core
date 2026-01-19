from ...uri import uri_to_path
from ...lsprotocol.client import Client, PublishDiagnosticsParams


class DocumentDiagnosticsMixins(Client):

    def handle_publish_diagnostics_notification(
        self, context: dict, params: PublishDiagnosticsParams
    ) -> None:
        file_name = uri_to_path(params["uri"])
        diagnostics = params["diagnostics"]

        documents = self.session.get_documents(lambda doc: doc.file_name == file_name)
        for document in documents:
            document.diagnostics = diagnostics
            self.session.diagnostic_manager.update(document.view, diagnostics)
