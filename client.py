"""client object"""

from __future__ import annotations

from .client_internal import BaseClient
from .features.initializer_mixin import InitializerMixin
from .features.text_document.synchronization_mixin import DocumentSynchronizerMixin
from .features.text_document.completion_mixin import DocumentCompletionMixin
from .features.text_document.signature_help_mixin import DocumentSignatureHelpMixin
from .features.text_document.hover_mixin import DocumentHoverMixin
from .features.text_document.formatting_mixin import DocumentFormattingMixin
from .features.text_document.definition_mixin import DocumentDefinitionMixin
from .features.text_document.rename_mixin import DocumentRenameMixin
from .features.text_document.diagnostics_mixin import DocumentDiagnosticsMixin
from .features.text_document.symbol_mixin import DocumentSymbolMixin
from .features.text_document.code_action_mixin import DocumentCodeActionMixin
from .features.workspace.execute_command_mixin import WorkspaceExecuteCommandMixin
from .features.workspace.apply_edit_mixin import WorkspaceApplyEditMixin
from .features.window.message_mixin import WindowMessageMixin


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

    def set_client_capabilities(self):
        super().set_client_capabilities()
