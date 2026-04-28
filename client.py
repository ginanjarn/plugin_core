"""client object"""

from __future__ import annotations

from typing import Any

from .client_internal import BaseClient
from .features.initializer import InitializerMixins
from .features.text_document.synchronization import DocumentSynchronizerMixins
from .features.text_document.completion import DocumentCompletionMixins
from .features.text_document.signature_help import DocumentSignatureHelpMixins
from .features.text_document.hover import DocumentHoverMixins
from .features.text_document.formatting import DocumentFormattingMixins
from .features.text_document.definition import DocumentDefinitionMixins
from .features.text_document.rename import DocumentRenameMixins
from .features.text_document.diagnostics import DocumentDiagnosticsMixins
from .features.text_document.symbol import DocumentSymbolMixins
from .features.text_document.code_action import DocumentCodeActionMixins
from .features.workspace.execute_command import WorkspaceExecuteCommandMixins
from .features.workspace.apply_edit import WorkspaceApplyEditMixins
from .features.window.message import WindowMessageMixins


class Singleton(type):
    _instance = None

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if not cls._instance:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


class Client(
    InitializerMixins,
    DocumentSynchronizerMixins,
    DocumentCompletionMixins,
    DocumentDefinitionMixins,
    DocumentDiagnosticsMixins,
    DocumentFormattingMixins,
    DocumentHoverMixins,
    DocumentRenameMixins,
    DocumentSignatureHelpMixins,
    DocumentSymbolMixins,
    DocumentCodeActionMixins,
    WorkspaceExecuteCommandMixins,
    WorkspaceApplyEditMixins,
    WindowMessageMixins,
    BaseClient,
    metaclass=Singleton,
):
    """Client Implementation"""
