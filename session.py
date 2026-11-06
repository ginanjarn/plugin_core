"""session object"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Any, Callable

from sublime import View

from .document import Document
from .features.text_document.diagnostic_reporter import (
    ReportManager as DiagnosticReportManager,
)
from .safe_dict import SafeDict

PathStr = str
LOGGER = logging.getLogger(__name__)


class SessionStatus(Enum):
    NotSet = 0
    Initializing = 1
    Initialized = 2
    Shutdown = 3


class DocumentMap(SafeDict):
    """Document Map"""


@dataclass
class Workspace:
    rootPath: PathStr
    configurations: dict = None
    diagnostics: dict = None


class Session:
    """Session Base class"""

    def __init__(self, **kwargs) -> None:
        self.client_capabilities: dict = {
            "textDocument": {},
            "workspace": {},
            "window": {},
        }
        self.server_capabilities: dict = {}
        self.status = SessionStatus.NotSet

        self.workspace_folders: List[Workspace] = []

        # In Sublime Text one buffer may associated to multiple view.
        # For example in 2 column layout, one file opened in 2 column.
        # Map 'working_documents' with View, it's easier to manage action target
        # such hover to decide where popup must be shown.
        self.opened_documents = DocumentMap()

        # Diagnostic manager
        self.diagnostic_reporter: DiagnosticReportManager = None

    def get_document(
        self, view: View, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        try:
            return self.opened_documents[view]
        except KeyError:
            return default

    def get_document_with_name(
        self, file_name: PathStr, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        for _, document in self.opened_documents.items():
            if document.file_name == file_name:
                return document
        return default

    def add_document(self, document: Document) -> None:
        self.opened_documents[document.view] = document

    def remove_document(self, view: View) -> None:
        try:
            del self.opened_documents[view]
        except KeyError as err:
            LOGGER.debug("document not found %s", err)

    def get_documents(
        self, filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Document]:
        """get documents."""

        if not filter_func:
            return [doc for _, doc in self.opened_documents.items()]
        return [doc for _, doc in self.opened_documents.items() if filter_func(doc)]

    def is_initialized(self):
        return self.status is SessionStatus.Initialized

    def reset(self):
        """"""
        self.opened_documents.clear()
        self.diagnostic_reporter = None
        self.status = SessionStatus.NotSet
