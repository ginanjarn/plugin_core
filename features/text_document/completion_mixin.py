from collections import defaultdict
from threading import Lock
from typing import List, Union, Optional

import sublime

from ...client_internal import BaseClient
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import CompletionList, CompletionItem


class _Empty:
    """Explicit empty value marker"""


EMPTY = _Empty()

# Map LSP completion kinds to Sublime kinds
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


class DocumentCompletionMixin(BaseClient):
    """Handles completion requests and caching."""

    AUTO_COMPLETE_ARGUMENTS = {
        "disable_auto_insert": True,
        "next_completion_if_showing": True,
        "auto_complete_commit_on_tab": True,
    }

    completion_target: Optional[object] = None
    _cached_completions: Union[List[sublime.CompletionItem], _Empty] = EMPTY
    _cached_completions_lock = Lock()

    def is_completions_available(self) -> bool:
        with self._cached_completions_lock:
            return self._cached_completions is not EMPTY

    def set_completions(self, completions: List[sublime.CompletionItem]) -> None:
        with self._cached_completions_lock:
            self._cached_completions = completions

    def pop_completions(self) -> List[sublime.CompletionItem]:
        with self._cached_completions_lock:
            completions = self._cached_completions
            self._cached_completions = EMPTY
            return completions if completions is not EMPTY else []

    @on_new_thread
    def textdocument_completion(self, view: sublime.View, row: int, col: int) -> None:
        """Request completions from the language server."""
        capabilities = self.session.server_capabilities.get("completionProvider")
        if not capabilities:
            return
        document = self.session.get_document(view)
        if document:
            self.completion_target = document
            self.completion_request(
                {
                    "position": {"character": col, "line": row},
                    "textDocument": {"uri": path_to_uri(document.file_name)},
                }
            )

    @on_main_thread
    def handle_completion_result(
        self, context: dict, result: Union[List[CompletionItem], CompletionList, None]
    ) -> None:
        """Handle completion results from LSP."""
        if not result:
            return

        try:
            if isinstance(result, list):
                items = [self._build_completion(item) for item in result]
            else:
                items = [
                    self._build_completion(item) for item in result.get("items", [])
                ]
        except Exception as e:
            print(f"[LSP Completion] Error building completions: {e}")
            return

        if items:
            self.set_completions(items)
            if self.completion_target and self.completion_target.view:
                self.completion_target.view.run_command(
                    "auto_complete", self.AUTO_COMPLETE_ARGUMENTS
                )

    @staticmethod
    def _build_completion(completion_item: CompletionItem) -> sublime.CompletionItem:
        """Convert LSP completion item to Sublime completion item."""
        label = completion_item.get("label", "")
        insert_text = (
            completion_item.get("textEdit", {}).get("newText")
            or completion_item.get("insertText")
            or label
        )
        detail = completion_item.get("detail", "")
        documentation = completion_item.get("documentation", "")
        kind = COMPLETION_KIND_MAP[completion_item.get("kind", 1)]

        annotation = detail or (documentation if isinstance(documentation, str) else "")
        return sublime.CompletionItem.snippet_completion(
            trigger=label,
            snippet=insert_text,
            annotation=annotation,
            kind=kind,
        )
