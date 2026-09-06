from collections import defaultdict
from threading import Lock
from typing import List, Union, Optional

import sublime
from sublime import KindId

from ...client_internal import BaseClient
from ...document import Document
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ...lsprotocol.client import CompletionList, CompletionItem


class _Empty:
    """Explicit empty value marker"""


EMPTY = _Empty()

# Map LSP completion kinds to Sublime kinds
LSP_TO_SUBLIME_KIND_MAP = defaultdict(
    lambda: sublime.KIND_AMBIGUOUS,
    {
        1: (KindId.COLOR_ORANGISH, "t", "Text"),  # text
        2: (KindId.FUNCTION, "", "Method"),  # method
        3: (KindId.FUNCTION, "", "Function"),  # function
        4: (KindId.FUNCTION, "c", "Constructor"),  # constructor
        5: (KindId.VARIABLE, "", "Field"),  # field
        6: (KindId.VARIABLE, "", "Variable"),  # variable
        7: (KindId.TYPE, "", "Class"),  # class
        8: (KindId.TYPE, "", "Interface"),  # interface
        9: (KindId.NAMESPACE, "", "Module"),  # module
        10: (KindId.VARIABLE, "", "Property"),  # property
        11: (KindId.TYPE, "", "Unit"),  # unit
        12: (KindId.COLOR_ORANGISH, "v", "Value"),  # value
        13: (KindId.TYPE, "", "Enum"),  # enum
        14: (KindId.KEYWORD, "", "Keyword"),  # keyword
        15: (KindId.SNIPPET, "s", "Snippet"),  # snippet
        16: (KindId.VARIABLE, "v", "Color"),  # color
        17: (KindId.VARIABLE, "p", "File"),  # file
        18: (KindId.VARIABLE, "p", "Reference"),  # reference
        19: (KindId.VARIABLE, "p", "Folder"),  # folder
        20: (KindId.VARIABLE, "v", "EnumMember"),  # enum member
        21: (KindId.VARIABLE, "c", "Constant"),  # constant
        22: (KindId.TYPE, "", "Struct"),  # struct
        23: (KindId.TYPE, "e", "Event"),  # event
        24: (KindId.KEYWORD, "", "Operator"),  # operator
        25: (KindId.TYPE, "", "TypeParameter"),  # type parameter
    },
)


class DocumentCompletionMixin(BaseClient):
    """Handles completion requests and caching."""

    _auto_complete_args = {
        "disable_auto_insert": True,
        "next_completion_if_showing": True,
        "auto_complete_commit_on_tab": True,
    }

    document_completion_target: Optional[Document] = None
    _cached_completions: Union[List[sublime.CompletionItem], _Empty] = EMPTY
    _cached_completions_lock = Lock()

    def completion_result_available(self) -> bool:
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
            self.document_completion_target = document
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
        if not (result and self.document_completion_target):
            return

        try:
            if isinstance(result, list):
                items = [self._build_completion_item(item) for item in result]
            else:
                items = [
                    self._build_completion_item(item)
                    for item in result.get("items", [])
                ]
        except Exception as e:
            print(f"[LSP Completion] Error building completions: {e}")
            return

        self.set_completions(items)
        self.document_completion_target.view.run_command(
            "auto_complete", self._auto_complete_args
        )

    @staticmethod
    def _build_completion_item(item: CompletionItem) -> sublime.CompletionItem:
        """Convert LSP completion item to Sublime completion item."""
        label = item.get("label", "")
        insert_text = (
            item.get("textEdit", {}).get("newText") or item.get("insertText") or label
        )
        detail = item.get("detail", "")
        documentation = item.get("documentation", "")
        kind = LSP_TO_SUBLIME_KIND_MAP[item.get("kind", 1)]

        annotation = detail or (documentation if isinstance(documentation, str) else "")
        return sublime.CompletionItem.snippet_completion(
            trigger=label,
            snippet=insert_text,
            annotation=annotation,
            kind=kind,
        )
