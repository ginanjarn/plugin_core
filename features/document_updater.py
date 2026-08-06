from dataclasses import dataclass
from typing import List

import sublime
import sublime_plugin

from ..document import TextChange


@dataclass
class _BufferedTextChange:
    region: sublime.Region
    old_text: str
    new_text: str

    __slots__ = ("region", "old_text", "new_text")


class _ApplyTextChangesCommand(sublime_plugin.TextCommand):
    """Apply text change command

    Changes items must serialized from 'TextChange'.
    """

    def run(self, edit: sublime.Edit, changes: List[dict]):
        text_changes = [self.to_text_change(c) for c in changes]
        self.apply(edit, text_changes)

    def apply(self, edit: sublime.Edit, text_changes: List[_BufferedTextChange]):
        # Apply text_changes from last to begin to ensure text changes don't
        # break change location
        for change in reversed(text_changes):
            self.view.replace(edit, change.region, change.new_text)

    def to_text_change(self, change: dict) -> _BufferedTextChange:
        text_point = self.view.text_point

        change = TextChange(**change)
        region = sublime.Region(text_point(*change.start), text_point(*change.end))
        old_text = self.view.substr(region)

        return _BufferedTextChange(region, old_text, change.text)
