import logging
import threading
from collections import defaultdict
from functools import wraps
from typing import Any, Dict, List, Optional, Set

import sublime
import sublime_plugin
from sublime import View

from .client import Client
from .document import TextChange
from .features.document_updater import _ApplyTextChangesCommandMixin
from .options import ClientOptions, ServerOptions
from .utils import debounce

LOGGER = logging.getLogger(__name__)


class LanguageSelector(str):
    """Sublime Text language selector.
    E.g.: source.python, source.c, text.html
    """


class Point(int):
    """"""


class Nothing:
    def __init__(self, *args, **kwargs):
        pass

    def __getattribute__(self, name: str, /) -> Any:
        return self

    def __call__(self, *args, **kwargs):
        pass


CLIENT_MAP: Dict[LanguageSelector, LanguageClient] = defaultdict(Nothing)


def get_lang_selector(view: View) -> LanguageSelector:
    return view.scope_name(0).split()[0]


def get_language_client(view: View) -> LanguageClient:
    """"""
    if not view.file_name():
        return Nothing()
    return CLIENT_MAP[get_lang_selector(view)]


def register_language_client(selector: LanguageSelector, lc: LanguageClient):
    """"""
    # Some server support multiple selectors.
    # For example clangd suport "source.c, source.c++"
    for sel in [s.strip() for s in selector.split(",")]:
        CLIENT_MAP[sel] = lc


def ignore_if_not_ready(method):
    @wraps(method)
    def inner(self, *args, **kwargs):
        if not self.client.is_ready():
            return None
        return method(self, *args, **kwargs)

    return inner


class LanguageClient:

    def __init__(
        self,
        selector: LanguageSelector,
        name: str,
        server_options: ServerOptions,
        client_options: ClientOptions,
    ) -> None:

        register_language_client(selector, self)
        self.client = Client(name, server_options, client_options)

        self._run_lock = threading.Lock()

    def start_server(self, view: View):
        if self.client.is_ready():
            return

        thread = threading.Thread(target=self._run_task, args=(view,))
        thread.start()

    @debounce(15)
    def _run_task(self, view: View):
        if self._run_lock.locked():
            return

        with self._run_lock:
            try:
                self.client.start_server()
                self.client.connect()

            except Exception as err:
                print("Start server error:", err)

            else:
                self.client.initialize(view)
                self.client.wait_initialized()
                self.client.textdocument_didopen(view)

    def terminate_server(self, view: View):
        self.client.shutdown()

    def initialize(self, view: View):
        self.client.initialize(view)

    @ignore_if_not_ready
    def document_didopen(self, view: View) -> None:
        self.client.textdocument_didopen(view)

    @ignore_if_not_ready
    def document_didopen_reload(self, view: View) -> None:
        self.client.textdocument_didopen(view, reload=True)

    @ignore_if_not_ready
    def document_didsave(self, view: View) -> None:
        self.client.textdocument_didsave(view)

    @ignore_if_not_ready
    def document_didclose(self, view: View) -> None:
        self.client.textdocument_didclose(view)

    @ignore_if_not_ready
    def document_didchange(self, view: View, changes: List[sublime.TextChange]) -> None:
        # Convert Sublime TextChange to our TextChange dataclass safely
        converted = [self.convert_text_change(c) for c in changes]
        self.client.textdocument_didchange(view, converted)

    def convert_text_change(self, c: sublime.TextChange):
        start = (c.a.row, c.a.col)
        end = (c.b.row, c.b.col)
        return TextChange(start, end, c.str, c.len_utf8)

    @ignore_if_not_ready
    def document_hover(
        self, view: View, point: int, hover_zone: sublime.HoverZone
    ) -> None:
        # Pointer may hover on inactive view. Sync opened document to server.
        if view != sublime.active_window().active_view():
            self.client.textdocument_didopen(view)

        row, col = view.rowcol(point)
        self.client.textdocument_hover(view, row, col)

    @ignore_if_not_ready
    def document_completion(
        self, view: View, prefix: str, locations: List[int]
    ) -> Optional[sublime.CompletionList]:
        location = min(locations)

        if self.client.completion_result_available():
            items = self.client.pop_completions()
            if (not items) or self._is_completion_context_changed(
                view, self.completion_trigger_point, location
            ):
                self.hide_completions(view)
                return None
            return sublime.CompletionList(items, flags=sublime.INHIBIT_WORD_COMPLETIONS)

        self.hide_completions(view)
        self.completion_trigger_point = location
        row, col = view.rowcol(location)
        self.client.textdocument_completion(view, row, col)
        return None

    def _is_completion_context_changed(
        self, view: sublime.View, old: int, new: int
    ) -> bool:
        """Check if completion context has changed."""
        if old == new:
            return False
        word = view.word(old)
        return not (new in word and view.substr(word).isidentifier())

    def hide_completions(self, view: sublime.View) -> None:
        view.run_command("hide_auto_complete")

    @ignore_if_not_ready
    def document_code_action(self, view: View, kinds: List[str] = None):
        self.client.textdocument_codeaction(view, view.sel()[0], kinds)

    @ignore_if_not_ready
    def document_definition(self, view: View) -> None:
        self.client.textdocument_definition(view)

    @ignore_if_not_ready
    def document_formatting(self, view: View) -> None:
        self.client.textdocument_formatting(view)

    @ignore_if_not_ready
    def document_prepare_rename(self, view: View) -> None:
        self.client.textdocument_preparerename(view)

    @ignore_if_not_ready
    def document_rename(self, view: View, row: int, column: int, new_name: str) -> None:
        self.client.textdocument_rename(view, row, column, new_name)

    @ignore_if_not_ready
    def document_signature_help(self, view: View) -> None:
        self.client.textdocument_signaturehelp(view)

    @ignore_if_not_ready
    def document_symbol(self, view: View) -> None:
        self.client.textdocument_symbol(view)

    @ignore_if_not_ready
    def workspace_execute_command(self, view: View, command: Dict[str, Any]) -> None:
        self.client.workspace_executecommand(command)


class PluginCoreEventListener(sublime_plugin.EventListener):

    @debounce(0.8)
    def on_activated(self, view: View):
        get_language_client(view).start_server(view)
        get_language_client(view).document_didopen(view)

    def on_reload_async(self, view: View):
        get_language_client(view).document_didopen_reload(view)

    def on_close(self, view: View):
        get_language_client(view).document_didclose(view)

    def on_query_completions(
        self, view: View, prefix: str, locations: List[Point]
    ) -> Optional[sublime.CompletionList]:
        return get_language_client(view).document_completion(view, prefix, locations)

    @debounce(0.8)
    def on_hover(self, view: View, point: Point, hover_zone: sublime.HoverZone):
        if hover_zone != sublime.HoverZone.TEXT:
            return
        get_language_client(view).document_hover(view, point, hover_zone)

    _signature_trigger_characters: Set[str]
    insert_commands = frozenset({"insert", "insert_snippet", "insert_completion"})

    @debounce(3)
    def on_modified_async(self, view: View) -> None:
        # Only react to insert-like commands to avoid triggering on non-insert edits
        name, *_ = view.command_history(0)
        if name not in self.insert_commands:
            return

        # get the character just inserted
        point = view.sel()[0].begin()
        if point == 0:
            return
        char = view.substr(point - 1)
        if char in self.signature_trigger_characters(view):
            get_language_client(view).document_signature_help(view)

    def signature_trigger_characters(self, view: View) -> Set[str]:
        if getattr(self, "_signature_trigger_characters", None):
            return self._signature_trigger_characters

        try:
            client = get_language_client(view).client
            capabilities = client.session.server_capabilities
            chars = capabilities["signatureHelpProvider"]["triggerCharacters"]
        except Exception:
            chars = ["("]

        self._signature_trigger_characters = set(chars)
        return self._signature_trigger_characters


class PluginCoreTextChangeListener(sublime_plugin.TextChangeListener):

    def on_text_changed(self, changes: List[sublime.TextChange]):
        view = self.buffer.primary_view()
        get_language_client(view).document_didchange(view, changes)


class PluginCoreApplyTextChangesCommand(
    _ApplyTextChangesCommandMixin, sublime_plugin.TextCommand
):
    def run(self, edit: sublime.Edit, changes: dict):
        self.apply_text_change(edit, changes)


class PluginCoreTextCommand(sublime_plugin.TextCommand):

    def run(
        self, edit: sublime.Edit, action: str, event: Optional[dict] = None, **kwargs
    ):
        lang_client = get_language_client(self.view)
        action_map = {
            "apply_text_change": None,  # Reimplement later
            "start_server": lang_client.start_server,
            "terminate_server": lang_client.terminate_server,
            "initialize": lang_client.initialize,
            "document_code_action": lang_client.document_code_action,
            "document_signature_help": lang_client.document_signature_help,
            "document_formatting": lang_client.document_formatting,
            "document_definition": lang_client.document_definition,
            "document_prepare_rename": lang_client.document_prepare_rename,
            "document_rename": lang_client.document_rename,
            "document_symbol": lang_client.document_symbol,
            "workspace_execute_command": lang_client.workspace_execute_command,
        }
        try:
            runner = action_map[action]
        except KeyError:
            print("Expected actions:", list(action_map.keys()))
            return

        # Reimplement later
        if action == "apply_text_change":
            self.view.run_command(
                "plugin_core_apply_text_changes", {"changes": kwargs["changes"]}
            )
            return

        self.move_selection(event)
        try:
            runner(self.view, **kwargs)
        except Exception as err:
            LOGGER.exception("command error: %s", err, exc_info=True)

    def move_selection(self, event: dict) -> None:
        if not event:
            return
        text_point = event.get("text_point")
        if text_point is None:
            return

        view_sel = self.view.sel
        # Move selection if text_point not in first selection
        selection = view_sel()[0]
        if not selection.contains(text_point):
            view_sel().clear()
            view_sel().add(text_point)

    def is_visible(self, action: str = "") -> bool:
        lang_client = get_language_client(self.view)
        if lang_client.client.is_ready():
            return True
        return False

    def want_event(self) -> bool:
        return True
