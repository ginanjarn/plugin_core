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
from .features.synchronization import (
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
from .features.workspace.execute_command import _WorkspaceExecuteCommandCommandMixin

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
    sublime_plugin.TextCommand,
    # comand implementation mixins
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
    _WorkspaceExecuteCommandCommandMixin,
    BasePlugin,
):

    non_initialized_actions = frozenset(
        {"start_server", "terminate_server", "initialize"}
    )

    def run(
        self, edit: sublime.Edit, action: str, event: Optional[dict] = None, **kwargs
    ):
        action_map = {
            "apply_text_change": self.apply_text_change,
            "start_server": self.start_server,
            "terminate_server": self.terminate_server,
            "initialize": self.initialize,
            "document_code_action": self.document_code_action,
            "document_signature_help": self.document_signature_help,
            "document_formatting": self.document_formatting,
            "document_definition": self.document_definition,
            "document_prepare_rename": self.document_prepare_rename,
            "document_rename": self.document_rename,
            "document_symbol": self.document_symbol,
            "workspace_execute_command": self.workspace_execute_command,
        }
        try:
            runner = action_map[action]
        except KeyError:
            print("expected actions:", list(action_map.keys()))
            return

        if event:
            view_sel = self.view.sel
            if text_point := event.get("text_point"):
                # move selection if text_point not in first selection
                if not view_sel()[0].contains(text_point):
                    view_sel().clear()
                    view_sel().add(sublime.Region(text_point))

        if action not in self.non_initialized_actions:
            if not self.client.is_ready():
                return

        try:
            runner(edit, **kwargs)
        except Exception as err:
            LOGGER.exception("command error: %s", err, exc_info=True)

    def is_visible(self, action: str = "") -> bool:
        if self.client and is_valid_document(self.view):
            if self.client.is_ready():
                return True
            return action in self.non_initialized_actions

        return False

    def want_event(self) -> bool:
        return True


class EventListener(
    sublime_plugin.ViewEventListener,
    # listener implementation mixins
    DocumentSynchronizeEventMixin,
    DocumentCompletionEventMixin,
    DocumentSignatureHelpEventMixin,
    DocumentHoverEventMixin,
    BasePlugin,
):

    @client_must_ready
    @must_valid_document
    def on_activated_async(self) -> None:
        self.document_didopen()

    @client_must_ready
    @must_valid_document
    def on_load_async(self) -> None:
        self.document_didopen_reload()

    @client_must_ready
    @must_valid_document
    def on_reload_async(self) -> None:
        self.document_didopen_reload()

    @client_must_ready
    @must_valid_document
    def on_revert_async(self) -> None:
        self.document_didopen_reload()

    @client_must_ready
    @must_valid_document
    def on_post_save_async(self) -> None:
        self.document_didsave()

    @client_must_ready
    @must_valid_document
    def on_close(self) -> None:
        self.document_didclose()

    @client_must_ready
    @must_valid_document
    def on_query_completions(
        self, prefix: str, locations: List[Point]
    ) -> Optional[sublime.CompletionList]:
        return self.document_completion(prefix, locations)

    @client_must_ready
    @must_valid_document
    def on_hover(self, point: Point, hover_zone: HoverZone):
        self.document_hover(point, hover_zone)

    @client_must_ready
    @must_valid_document
    def on_modified_async(self) -> None:
        self.document_signature_help()


class TextChangeListener(
    sublime_plugin.TextChangeListener,
    # listener implementation mixins
    DocumentChangeEventMixin,
    BasePlugin,
):

    @client_must_ready
    def on_text_changed(self, changes: List[sublime.TextChange]):
        if not is_valid_document(self.buffer.primary_view()):
            return
        self.document_didchange(changes)
