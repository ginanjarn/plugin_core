"""client object"""

import logging

from .features.initializer_mixin import InitializerMixin
from .features.synchronization_mixin import DocumentSynchronizerMixin
from .features.text_document.code_action_mixin import DocumentCodeActionMixin
from .features.text_document.completion_mixin import DocumentCompletionMixin
from .features.text_document.definition_mixin import DocumentDefinitionMixin
from .features.text_document.diagnostics_mixin import DocumentDiagnosticsMixin
from .features.text_document.formatting_mixin import DocumentFormattingMixin
from .features.text_document.hover_mixin import DocumentHoverMixin
from .features.text_document.rename_mixin import DocumentRenameMixin
from .features.text_document.signature_help_mixin import DocumentSignatureHelpMixin
from .features.text_document.symbol_mixin import DocumentSymbolMixin
from .features.window.message_mixin import WindowMessageMixin
from .features.workspace.apply_edit_mixin import WorkspaceApplyEditMixin
from .features.workspace.execute_command_mixin import WorkspaceExecuteCommandMixin
from .options import ClientOptions, ServerOptions
from .rpc import RPC

LOGGER = logging.getLogger(__name__)


class Client(
    RPC,
    InitializerMixin,
    DocumentSynchronizerMixin,
    DocumentCompletionMixin,
    DocumentDefinitionMixin,
    DocumentDiagnosticsMixin,
    DocumentFormattingMixin,
    DocumentHoverMixin,
    DocumentRenameMixin,
    DocumentSignatureHelpMixin,
    DocumentSymbolMixin,
    DocumentCodeActionMixin,
    WorkspaceExecuteCommandMixin,
    WorkspaceApplyEditMixin,
    WindowMessageMixin,
):
    """Client Implementation"""

    def __init__(
        self,
        name: str,
        server_options: ServerOptions,
        client_options: ClientOptions,
    ):
        super().__init__(server_options.get_transport())
        self.server_process = server_options.get_process()

        self.client_name = name
        self.server_options = server_options
        self.client_options = client_options

        self.set_client_capabilities()

    def set_client_capabilities(self):
        super().set_client_capabilities()

    def start_server(self):
        """Start server process"""
        self.server_process.run(self.server_options.get_options())

    def shutdown(self) -> None:
        """Shutdown the server process."""
        try:
            self.shutdown_request(None)
            self.exit_notification(None)
        except Exception as err:
            LOGGER.warning("Error sending shutdown/exit: %s", err)
        finally:
            self.server_process.terminate()
