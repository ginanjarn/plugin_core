"""session object"""

import logging
import threading
from enum import Enum
from typing import Optional, Dict, List, Any, Callable

from sublime import View

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

        # In Sublime Text one buffer may associated to multiple view.
        # For example in 2 column layout, one file opened in 2 column.
        # Map 'working_documents' with View, it's easier to manage action target
        # such hover to decide where popup must be shown.

        self.working_documents: Dict[View, Document] = {}
        self._working_documents_lock = threading.Lock()

        # Diagnostic manager
        self.diagnostic_manager = DiagnosticManager(kwargs.get("report_settings"))

    def get_document(
        self, view: View, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        with self._working_documents_lock:
            try:
                return self.working_documents[view]
            except KeyError:
                return default

    def get_document_with_name(
        self, file_name: PathStr, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        with self._working_documents_lock:
            for _, document in self.working_documents.items():
                if document.file_name == file_name:
                    return document
            return default

    def add_document(self, document: Document) -> None:
        with self._working_documents_lock:
            self.working_documents[document.view] = document

    def remove_document(self, view: View) -> None:
        with self._working_documents_lock:
            try:
                del self.working_documents[view]
            except KeyError as err:
                LOGGER.debug("document not found %s", err)
                pass

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
