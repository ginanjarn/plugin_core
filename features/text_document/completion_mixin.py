from collections import defaultdict
from threading import Lock
from typing import List, Optional, Union

import sublime
from sublime import KindId

from ...document import Document
from ...lsprotocol.client import CompletionItem, CompletionList
from ...uri import path_to_uri
from ...utils import on_main_thread, on_new_thread
from ..base_feature import BaseFeature, require_server_capability


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


class CompletionBuffer:
    def __init__(self) -> None:
        self._items = []
        self._lock = Lock()

    def is_available(self) -> bool:
        with self._lock:
            return self._items is not EMPTY

    def set(self, items: List[sublime.CompletionItem]) -> None:
        with self._lock:
            self._items = items

    def pop(self) -> List[sublime.CompletionItem]:
        with self._lock:
            completions = self._items
            if completions is EMPTY:
                return []

            self._items = EMPTY
            return completions


class DocumentCompletionMixin(BaseFeature):
    """Handles completion requests and caching."""

    _auto_complete_args = {
        "disable_auto_insert": True,
        "next_completion_if_showing": True,
        "auto_complete_commit_on_tab": True,
    }

    document_completion_target: Optional[Document]
    _completion_buffer: CompletionBuffer

    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["textDocument"].update(
            {
                "completion": {
                    "dynamicRegistration": False,
                    "completionItem": {
                        "snippetSupport": True,
                        "commitCharactersSupport": False,
                        "documentationFormat": [],
                        "deprecatedSupport": False,
                        "preselectSupport": False,
                        "tagSupport": {"valueSet": [1]},
                        "insertReplaceSupport": False,
                        "resolveSupport": {"properties": []},
                        "insertTextModeSupport": {"valueSet": [1, 2]},
                        "labelDetailsSupport": True,
                    },
                    "completionItemKind": {
                        "valueSet": [
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            7,
                            8,
                            9,
                            10,
                            11,
                            12,
                            13,
                            14,
                            15,
                            16,
                            17,
                            18,
                            19,
                            20,
                            21,
                            22,
                            23,
                            24,
                            25,
                        ]
                    },
                    "insertTextMode": 1,
                    "contextSupport": False,
                    "completionList": {"itemDefaults": [], "applyKindSupport": False},
                },
            }
        )

    @property
    def completion_buffer(self) -> CompletionBuffer:
        if not getattr(self, "_completion_buffer", None):
            self._completion_buffer = CompletionBuffer()
        return self._completion_buffer

    def completion_result_available(self) -> bool:
        return self.completion_buffer.is_available()

    def pop_completions(self) -> List[sublime.CompletionItem]:
        return self.completion_buffer.pop()

    @on_new_thread
    @require_server_capability("completionProvider")
    def textdocument_completion(self, view: sublime.View, row: int, col: int) -> None:
        """Request completions from the language server."""

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

        self.completion_buffer.set(items)
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
