from collections import namedtuple
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

import sublime
import sublime_plugin

from ..document import TextChange
from ..session import Session
from ..uri import uri_to_path
from ...constant import COMMAND_PREFIX


LineCharacter = namedtuple("LineCharacter", ["line", "character"])
PathStr = str


class Workspace:
    """Workspace"""

    def __init__(self, session: Session):
        self.session = session

    def apply_document_changes(self, changes: List[dict]):
        for change in changes:
            self._apply_change(change)

    def _apply_change(self, change: dict) -> None:
        # change type must one of TextDocumentEdit|CreateFile|RenameFile|DeleteFile
        if "kind" in change:
            # CreateFile | RenameFile | DeleteFile
            self._apply_resource_change(change)
        else:
            # TextDocumentEdit
            self._apply_text_document_edit(change)

    def _apply_resource_change(self, resource_changes: dict) -> None:
        resource_change_map = {
            "create": self._create_document,
            "rename": self._rename_document,
            "delete": self._delete_document,
        }
        kind = resource_changes["kind"]
        resource_change_map[kind](resource_changes)

    def _apply_text_document_edit(self, text_document_edit: dict):
        file_name = uri_to_path(text_document_edit["textDocument"]["uri"])
        text_changes = [rpc_to_textchange(c) for c in text_document_edit["edits"]]

        if document := self.session.get_document_with_name(file_name):
            view = document.view
            self._apply_view_changes(view, text_changes)
            view.run_command("save")
        else:
            TextFile(file_name).apply_text_changes(text_changes)

    @staticmethod
    def _apply_view_changes(view: sublime.View, text_changes: List[TextChange]):
        view.run_command(
            f"{COMMAND_PREFIX}_apply_text_changes",
            {"changes": [asdict(c) for c in text_changes]},
        )

    @staticmethod
    def _create_document(resource_changes: dict):
        file_name = uri_to_path(resource_changes["textDocument"]["uri"])
        Path(file_name).touch(exist_ok=True)

    @staticmethod
    def _rename_document(resource_changes: dict):
        old = uri_to_path(resource_changes["oldUri"])
        new = uri_to_path(resource_changes["newUri"])
        Path(old).rename(new)

        # retarget buffer to new path
        for view in [
            v for v in sublime.active_window().views() if v.file_name() == old
        ]:
            view.retarget(new)

    @staticmethod
    def _delete_document(resource_changes: dict):
        file_name = uri_to_path(resource_changes["textDocument"]["uri"])
        Path(file_name).unlink()

        # close opened view
        for view in [
            v for v in sublime.active_window().views() if v.file_name() == file_name
        ]:
            view.close()


def rpc_to_textchange(change: dict) -> TextChange:
    """"""
    return TextChange(
        LineCharacter(**change["range"]["start"]),
        LineCharacter(**change["range"]["end"]),
        change["newText"],
        change.get("rangeLength", 0),
    )


class TextFile:

    def __init__(self, file_name: PathStr) -> None:
        self.path = Path(file_name)

    def apply_text_changes(self, text_changes: List[TextChange]) -> None:
        try:
            old_text = self.path.read_text()
        except FileNotFoundError:
            old_text = ""

        new_text = self._apply_text_changes(old_text, text_changes)
        self.path.write_text(new_text)

    def _get_offset(self, lines: List[str], row: int, column: int) -> int:
        line_offset = sum([len(l) for l in lines[:row]])
        return line_offset + column

    def _apply_text_changes(self, source: str, text_changes: List[TextChange]) -> str:
        temp = source

        for change in text_changes:
            lines = temp.splitlines(keepends=True)
            start_offset = self._get_offset(lines, *change.start)
            end_offset = self._get_offset(lines, *change.end)

            temp = f"{temp[:start_offset]}{change.text}{temp[end_offset:]}"

        return temp


@dataclass
class _BufferedTextChange:
    region: sublime.Region
    old_text: str
    new_text: str

    __slots__ = ("region", "old_text", "new_text")

    def offset_move(self) -> int:
        return len(self.new_text) - len(self.old_text)

    def get_moved_region(self, move: int) -> sublime.Region:
        a, b = self.region.to_tuple()
        return sublime.Region(a + move, b + move)


class _ApplyTextChangesCommand(sublime_plugin.TextCommand):
    """Apply text change command

    Changes items must serialized from 'TextChange'.
    """

    def run(self, edit: sublime.Edit, changes: List[dict]):
        text_changes = [self.to_text_change(c) for c in changes]
        self.apply(edit, text_changes)

    def apply(self, edit: sublime.Edit, text_changes: List[_BufferedTextChange]):
        move = 0
        for change in text_changes:
            replaced_region = change.get_moved_region(move)
            self.view.replace(edit, replaced_region, change.new_text)
            move += change.offset_move()

    def to_text_change(self, change: dict) -> _BufferedTextChange:
        text_point = self.view.text_point

        change = TextChange(**change)
        region = sublime.Region(text_point(*change.start), text_point(*change.end))
        old_text = self.view.substr(region)

        return _BufferedTextChange(region, old_text, change.text)
