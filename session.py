"""session object"""

import logging
import threading
from collections.abc import MutableMapping
from functools import wraps
from enum import Enum
from typing import Optional, List, Any, Callable, Iterator

from sublime import View

from ..constant import LOGGING_CHANNEL
from .document import Document
from .features.text_document.diagnostics import PublishDiagnosticReporter


MethodName = str
PathStr = str
LOGGER = logging.getLogger(LOGGING_CHANNEL)


class InitializeStatus(Enum):
    NotInitialized = 0
    Initializing = 1
    Initialized = 2


class DocumentMap(MutableMapping):
    """Document Map

    In Sublime Text one buffer may associated to multiple view.
    For example in 2 column layout, one file opened in 2 column.
    Map 'working_documents' with View, it's easier to manage action target
    such hover to decide where popup must be shown.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.data = dict(*args, **kwargs)
        self._lock = threading.Lock()

    def lock(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            with self._lock:
                return func(*args, **kwargs)

        return wrapper

    @lock
    def __setitem__(self, key: View, value: Document) -> None:
        self.data[key] = value

    @lock
    def __getitem__(self, key: View) -> Document:
        return self.data[key]

    @lock
    def __delitem__(self, key: View) -> None:
        del self.data[key]

    @lock
    def __iter__(self) -> Iterator[View]:
        yield from iter(self.data)


class Session:
    """Session Base class"""

    def __init__(self, **kwargs) -> None:
        self.client_capabilities: dict = {}
        self.server_capabilities: dict = {}
        self.initialize_status = InitializeStatus.NotInitialized

        self.workspace_path: PathStr = ""
        self.working_documents: DocumentMap = {}

        # Diagnostic manager
        self.diagnostic_manager = PublishDiagnosticReporter(kwargs.get("report_settings"))

    def get_document(
        self, view: View, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        try:
            return self.working_documents[view]
        except KeyError:
            return default

    def get_document_with_name(
        self, file_name: PathStr, /, default: Optional[Any] = None
    ) -> Optional[Document]:
        for _, document in self.working_documents.items():
            if document.file_name == file_name:
                return document
        return default

    def add_document(self, document: Document) -> None:
        self.working_documents[document.view] = document

    def remove_document(self, view: View) -> None:
        try:
            del self.working_documents[view]
        except KeyError as err:
            LOGGER.debug("document not found %s", err)

    def get_documents(
        self, filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Document]:
        """get documents."""

        if not filter_func:
            return [doc for _, doc in self.working_documents.items()]
        return [doc for _, doc in self.working_documents.items() if filter_func(doc)]

    def is_initialized(self):
        return self.initialize_status is InitializeStatus.Initialized

    def reset(self):
        """"""
        self.working_documents.clear()
        self.diagnostic_manager.reset()
        self.initialize_status = InitializeStatus.NotInitialized
