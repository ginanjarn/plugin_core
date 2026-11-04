"""client object"""

from .base_client import BaseClient
from .child_process import ChildProcess
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
from .transport import Transport


class Client(
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
    BaseClient,
):
    """Client Implementation"""

    def __init__(
        self,
        process: ChildProcess,
        transport: Transport,
    ):
        super().__init__(process, transport)

    def set_client_capabilities(self):
        super().set_client_capabilities()
