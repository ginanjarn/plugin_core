"""Document module"""

import threading
import time
from collections import namedtuple
from dataclasses import dataclass
from typing import List

import sublime

from ..constant import LANGUAGE_ID, VIEW_SELECTOR


def is_valid_document(view: sublime.View) -> bool:
    """check if view is valid document"""
    return bool(view.file_name()) and view.match_selector(0, VIEW_SELECTOR)


RowColumn = namedtuple("RowColumn", ["row", "column"])


@dataclass
class TextChange:
    start: RowColumn
    end: RowColumn
    text: str
    length: int

    __slots__ = ("start", "end", "text", "length")


class Document:

    def __init__(self, view: sublime.View):
        self.view = view
        self.file_name = self.view.file_name()
        self.language_id = LANGUAGE_ID
        self.diagnostics: List[dict] = []

        self._cached_completion = None
        self._cached_completion_lock = threading.Lock()

    def window(self) -> sublime.Window:
        return self.view.window()

    @property
    def version(self) -> int:
        return self.view.change_count()

    @property
    def text(self):
        # wait until complete loaded
        while self.view.is_loading():
            time.sleep(0.5)

        return self.view.substr(sublime.Region(0, self.view.size()))

    def set_completion(self, items: List[sublime.CompletionItem]):
        with self._cached_completion_lock:
            self._cached_completion = items

    def pop_completion(self) -> List[sublime.CompletionItem]:
        with self._cached_completion_lock:
            temp = self._cached_completion
            self._cached_completion = None
            return temp

    def is_completion_available(self) -> bool:
        with self._cached_completion_lock:
            return self._cached_completion is not None
