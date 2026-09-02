"""plugin base"""

import logging
from functools import wraps
from typing import List, Optional

import sublime
import sublime_plugin
from sublime import HoverZone

from .client_internal import BaseClient
from .registry import VIEW_SELECTOR
from .features.document_updater import _ApplyTextChangesCommandMixin
from .features.server_manager import (
    _StartServerCommandMixin,
    _TerminateServerCommandMixin,
)
from .features.initializer import _InitializeCommandMixin
from .features.text_document.synchronization import (
    DocumentSynchronizeEventMixin,
    DocumentChangeEventMixin,
)
from .features.text_document.code_action import _DocumentCodeActionCommandMixin
from .features.text_document.completion import DocumentCompletionEventMixin
from .features.text_document.signature_help import (
    _DocumentSignatureHelpCommandMixin,
    DocumentSignatureHelpEventMixin,
)
from .features.text_document.hover import DocumentHoverEventMixin
from .features.text_document.formatting import _DocumentFormattingCommandMixin
from .features.text_document.definition import _DocumentDefinitionCommandMixin
from .features.text_document.rename import (
    _DocumentPrepareRenameCommandMixin,
    _DocumentRenameCommandMixin,
)
from .features.text_document.symbol import _DocumentSymbolCommandMixin

LOGGER = logging.getLogger(__name__)
Point = int


class BasePlugin:
    client: Optional[BaseClient] = None


def client_must_ready(func):
    """client must ready to call function"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


def is_valid_document(view: sublime.View) -> bool:
    """check if view is valid document"""
    return bool(view.file_name()) and view.match_selector(0, VIEW_SELECTOR)


def must_valid_document(func):
    """document must valid to call function"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if is_valid_document(self.view):
            return func(self, *args, **kwargs)
        return None

    return wrapper


class _BaseTextCommand(
    _ApplyTextChangesCommandMixin,
    _StartServerCommandMixin,
    _TerminateServerCommandMixin,
    _InitializeCommandMixin,
    _DocumentCodeActionCommandMixin,
    _DocumentSignatureHelpCommandMixin,
    _DocumentFormattingCommandMixin,
    _DocumentDefinitionCommandMixin,
    _DocumentPrepareRenameCommandMixin,
    _DocumentRenameCommandMixin,
    _DocumentSymbolCommandMixin,
    BasePlugin,
    sublime_plugin.TextCommand,
):
    action_map = {
        "apply_text_change": _ApplyTextChangesCommandMixin,
        "start_server": _StartServerCommandMixin,
        "terminate_server": _TerminateServerCommandMixin,
        "initialize": _InitializeCommandMixin,
        "document_code_action": _DocumentCodeActionCommandMixin,
        "document_signature_help": _DocumentSignatureHelpCommandMixin,
        "document_formatting": _DocumentFormattingCommandMixin,
        "document_definition": _DocumentDefinitionCommandMixin,
        "document_prepare_rename": _DocumentPrepareRenameCommandMixin,
        "document_rename": _DocumentRenameCommandMixin,
        "document_symbol": _DocumentSymbolCommandMixin,
    }

    def run(
        self, edit: sublime.Edit, action: str, event: Optional[dict] = None, **kwargs
    ):
        try:
            runner = self.action_map[action]
        except KeyError:
            print("expected actions:", list(self.action_map.keys()))
            return

        if event:
            view_sel = self.view.sel
            if text_point := event.get("text_point"):
                view_sel().clear()
                view_sel().add(sublime.Region(text_point))

        if action not in {"start_server", "terminate_server", "initialize"}:
            if not self.client.is_ready():
                return

        try:
            runner.run(self, edit, **kwargs)
        except Exception as err:
            LOGGER.exception("command error: %s", err, exc_info=True)

    def is_visible(self) -> bool:
        return is_valid_document(self.view)

    def want_event(self) -> bool:
        return True


class EventListerer(
    DocumentSynchronizeEventMixin,
    DocumentCompletionEventMixin,
    DocumentSignatureHelpEventMixin,
    DocumentHoverEventMixin,
    BasePlugin,
    sublime_plugin.ViewEventListener,
):
    def __init__(self, view: sublime.View):
        super().__init__(view)

    @client_must_ready
    @must_valid_document
    def on_activated_async(self) -> None:
        DocumentSynchronizeEventMixin.on_activated_async(self)

    @client_must_ready
    @must_valid_document
    def on_load_async(self) -> None:
        DocumentSynchronizeEventMixin.on_load_async(self)

    @client_must_ready
    @must_valid_document
    def on_reload_async(self) -> None:
        DocumentSynchronizeEventMixin.on_reload_async(self)

    @client_must_ready
    @must_valid_document
    def on_revert_async(self) -> None:
        DocumentSynchronizeEventMixin.on_revert_async(self)

    @client_must_ready
    @must_valid_document
    def on_post_save_async(self) -> None:
        DocumentSynchronizeEventMixin.on_post_save_async(self)

    @client_must_ready
    @must_valid_document
    def on_close(self) -> None:
        DocumentSynchronizeEventMixin.on_close(self)

    @client_must_ready
    @must_valid_document
    def on_query_completions(
        self, prefix: str, locations: List[Point]
    ) -> Optional[sublime.CompletionList]:
        return DocumentCompletionEventMixin.on_query_completions(
            self, prefix, locations
        )

    @client_must_ready
    @must_valid_document
    def on_modified_async(self) -> None:
        DocumentSignatureHelpEventMixin.on_modified_async(self)

    @client_must_ready
    @must_valid_document
    def on_selection_modified_async(self) -> None:
        DocumentSignatureHelpEventMixin.on_selection_modified_async(self)

    @client_must_ready
    @must_valid_document
    def on_hover(self, point: Point, hover_zone: HoverZone):
        DocumentHoverEventMixin.on_hover(self, point, hover_zone)


class TextChangeListener(
    DocumentChangeEventMixin,
    BasePlugin,
    sublime_plugin.TextChangeListener,
):
    def __init__(self):
        super().__init__()

    @client_must_ready
    def on_text_changed(self, changes: List[sublime.TextChange]):
        if not is_valid_document(self.buffer.primary_view()):
            return
        DocumentChangeEventMixin.on_text_changed(self, changes)
