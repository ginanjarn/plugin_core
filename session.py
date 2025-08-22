"""session object"""

import logging
import threading
from enum import Enum
from typing import Optional, Dict, List, Any, Callable

import sublime

from ..constant import LOGGING_CHANNEL
from .document import Document
from .diagnostics import DiagnosticManager


MethodName = str
PathStr = str
LOGGER = logging.getLogger(LOGGING_CHANNEL)


class SessionBase:
    """Session Base class"""

    def __init__(self, **kwargs) -> None:
        # prevent inherited class call 'object.__init__'
        pass


class DocumentManager(SessionBase):
    """"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.working_documents: Dict[PathStr, Document] = {}
        self._working_documents_lock = threading.Lock()

        # Diagnostic manager
        self.diagnostic_manager = DiagnosticManager(kwargs.get("report_settings"))

    def get_document(
        self, file_name: PathStr, /, default: Any = None
    ) -> Optional[Document]:
        with self._working_documents_lock:
            try:
                return self.working_documents[file_name]
            except KeyError:
                return default

    def add_document(self, document: Document) -> None:
        with self._working_documents_lock:
            self.working_documents[document.file_name] = document

    def remove_document(self, file_name: PathStr) -> None:
        with self._working_documents_lock:
            try:
                del self.working_documents[file_name]
            except KeyError as err:
                LOGGER.debug("document not found %s", err)
                pass

    def get_document_by_view(
        self, view: sublime.View, /, default: Any = None
    ) -> Optional[Document]:
        """get document by view"""

        with self._working_documents_lock:
            for _, document in self.working_documents.items():
                if document.view == view:
                    return document
            return default

    def get_documents(
        self, filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Document]:
        """get documents."""

        with self._working_documents_lock:
            if not filter_func:
                return [doc for _, doc in self.working_documents.items()]
            return [
                doc for _, doc in self.working_documents.items() if filter_func(doc)
            ]

    def reset_document_manager(self):
        with self._working_documents_lock:
            self.working_documents.clear()
            self.diagnostic_manager.reset()


class InitializeStatus(Enum):
    NotInitialized = 0
    Initializing = 1
    Initialized = 2


class InitializeManager(SessionBase):
    """"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._initialize_status = InitializeStatus.NotInitialized

    def is_initializing(self) -> bool:
        return self._initialize_status is InitializeStatus.Initializing

    def is_initialized(self) -> bool:
        return self._initialize_status is InitializeStatus.Initialized

    def set_initialize_status(self, status: InitializeStatus) -> None:
        self._initialize_status = InitializeStatus(status)

    def reset_initialize_manager(self):
        self._initialize_status = InitializeStatus.NotInitialized


class Session(DocumentManager, InitializeManager):
    """Session"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def reset(self):
        """"""
        self.reset_document_manager()
        self.reset_initialize_manager()
