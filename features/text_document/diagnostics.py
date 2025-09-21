from ...session import Session
from ...uri import uri_to_path


class DocumentDiagnosticsMixins:

    def handle_textdocument_publishdiagnostics(self, session: Session, params: dict):
        file_name = uri_to_path(params["uri"])
        diagnostics = params["diagnostics"]

        documents = session.get_documents(lambda doc: doc.file_name == file_name)
        for document in documents:
            document.diagnostics = diagnostics
            session.diagnostic_manager.update(document.view, diagnostics)
