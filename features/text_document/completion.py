from collections import defaultdict
from functools import wraps
from threading import Lock
from typing import List, Union
import sublime
import sublime_plugin

from ...document import is_valid_document
from ...uri import path_to_uri
from ...lsprotocol.client import Client, CompletionList, CompletionItem


class _Empty:
    """Explicit empty value"""


EMPTY = _Empty()

COMPLETION_KIND_MAP = defaultdict(
    lambda: sublime.KIND_AMBIGUOUS,
    {
        1: (sublime.KindId.COLOR_ORANGISH, "t", ""),  # text
        2: (sublime.KindId.FUNCTION, "", ""),  # method
        3: (sublime.KindId.FUNCTION, "", ""),  # function
        4: (sublime.KindId.FUNCTION, "c", ""),  # constructor
        5: (sublime.KindId.VARIABLE, "", ""),  # field
        6: (sublime.KindId.VARIABLE, "", ""),  # variable
        7: (sublime.KindId.TYPE, "", ""),  # class
        8: (sublime.KindId.TYPE, "", ""),  # interface
        9: (sublime.KindId.NAMESPACE, "", ""),  # module
        10: (sublime.KindId.VARIABLE, "", ""),  # property
        11: (sublime.KindId.TYPE, "", ""),  # unit
        12: (sublime.KindId.COLOR_ORANGISH, "v", ""),  # value
        13: (sublime.KindId.TYPE, "", ""),  # enum
        14: (sublime.KindId.KEYWORD, "", ""),  # keyword
        15: (sublime.KindId.SNIPPET, "s", ""),  # snippet
        16: (sublime.KindId.VARIABLE, "v", ""),  # color
        17: (sublime.KindId.VARIABLE, "p", ""),  # file
        18: (sublime.KindId.VARIABLE, "p", ""),  # reference
        19: (sublime.KindId.VARIABLE, "p", ""),  # folder
        20: (sublime.KindId.VARIABLE, "v", ""),  # enum member
        21: (sublime.KindId.VARIABLE, "c", ""),  # constant
        22: (sublime.KindId.TYPE, "", ""),  # struct
        23: (sublime.KindId.TYPE, "e", ""),  # event
        24: (sublime.KindId.KEYWORD, "", ""),  # operator
        25: (sublime.KindId.TYPE, "", ""),  # type parameter
    },
)


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentCompletionMixins(Client):

    AUTO_COMPLETE_ARGUMENTS = {
        "disable_auto_insert": True,
        "next_completion_if_showing": True,
        "auto_complete_commit_on_tab": True,
    }

    completion_target = None

    _cached_completions: List[sublime.CompletionItem] = EMPTY
    _cached_completions_lock = Lock()

    def is_completions_available(self) -> bool:
        with self._cached_completions_lock:
            return self._cached_completions is not EMPTY

    def set_completions(self, completions: List[sublime.CompletionItem]):
        with self._cached_completions_lock:
            self._cached_completions = completions

    def pop_completions(self) -> List[sublime.CompletionItem]:
        with self._cached_completions_lock:
            completions = self._cached_completions
            self._cached_completions = EMPTY
            return completions

    @must_initialized
    def textdocument_completion(self, view: sublime.View, row: int, col: int):
        capabilities = self.session.server_capabilities.get("completionProvider", None)
        if not capabilities:
            return
        if document := self.session.get_document(view):
            self.completion_target = document
            self.completion_request(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                },
            )

    def handle_completion_result(
        self, context: dict, result: Union[List[CompletionItem], CompletionList, None]
    ) -> None:
        if not result:
            return

        if isinstance(result, list):
            items = [self._build_completion(item) for item in result]
        else:
            items = [self._build_completion(item) for item in result["items"]]

        self.set_completions(items)
        view = self.completion_target.view
        view.run_command("auto_complete", self.AUTO_COMPLETE_ARGUMENTS)

    @staticmethod
    def _build_completion(completion_item: CompletionItem) -> sublime.CompletionItem:
        label = completion_item["label"]
        try:
            insert_text = completion_item["textEdit"]["newText"]
        except KeyError:
            insert_text = label

        detail = completion_item.get("detail", "")
        kind = COMPLETION_KIND_MAP[completion_item.get("kind", 1)]

        return sublime.CompletionItem.snippet_completion(
            trigger=label,
            snippet=insert_text,
            annotation=detail,
            kind=kind,
        )


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class CompletionEventListener(sublime_plugin.EventListener):
    client: DocumentCompletionMixins = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_trigger_location = 0

    @client_must_ready
    def on_query_completions(
        self, view: sublime.View, prefix: str, locations: List[int]
    ) -> sublime.CompletionList:
        if not is_valid_document(view):
            return None

        # trigger on first location
        location = min(locations)

        if self.client.is_completions_available():
            items = self.client.pop_completions()
            if (not items) or self._is_context_changed(
                view, self.prev_trigger_location, location
            ):
                self.hide_completions(view)
                return None

            return sublime.CompletionList(items, flags=sublime.INHIBIT_WORD_COMPLETIONS)

        self.prev_trigger_location = location

        row, col = view.rowcol(location)
        self.client.textdocument_completion(view, row, col)
        self.hide_completions(view)

        return None

    def _is_context_changed(self, view: sublime.View, old: int, new: int) -> bool:
        """check if context moved from old point"""

        # point unchanged
        if old == new:
            return False
        # point changed but still in same word
        word = view.word(old)
        if new in word and view.substr(word).isidentifier():
            return False

        return True

    def hide_completions(self, view: sublime.View):
        view.run_command("hide_auto_complete")
