import logging
from collections import namedtuple
from dataclasses import asdict
from pathlib import Path
from typing import List, Iterator

import sublime

from ....constant import LOGGING_CHANNEL, COMMAND_PREFIX
from ...document import TextChange
from ...session import Session
from ...uri import uri_to_path

LOGGER = logging.getLogger(LOGGING_CHANNEL)
PathStr = str


class WorkspaceApplyEditMixins:
    def handle_workspace_applyedit(self, session: Session, params: dict) -> dict:
        try:
            changes = self._get_changes(params["edit"])
            WorkspaceEdit(session).apply_changes(changes)

        except Exception as err:
            LOGGER.error(err, exc_info=True)
            return {"applied": False}
        else:
            return {"applied": True}

    def _get_changes(self, edit: dict) -> Iterator[dict]:
        for document_changes in edit["documentChanges"]:
            yield document_changes


LineCharacter = namedtuple("LineCharacter", ["line", "character"])


class WorkspaceEdit:

    def __init__(self, session: Session):
        self.session = session

    def apply_changes(self, document_changes_items: List[dict]):
        for change in document_changes_items:
            self._apply_changes(change)

    def _apply_changes(self, changes: dict) -> None:
        # changes: TextEdit|CreateFile|RenameFile|DeleteFile

        if "kind" in changes:
            # File Resource Changes
            self._apply_resource_changes(changes)
        else:
            # TextEdit Changes
            self._apply_edit_changes(changes)

    def _apply_resource_changes(self, resource_changes: dict) -> None:
        resource_change_map = {
            "create": self._create_document,
            "rename": self._rename_document,
            "delete": self._delete_document,
        }
        kind = resource_changes["kind"]
        resource_change_map[kind](resource_changes)

    def _apply_edit_changes(self, document_changes: dict):
        file_name = uri_to_path(document_changes["textDocument"]["uri"])
        changes = [rpc_to_textchange(c) for c in document_changes["edits"]]

        if document := self.session.get_document(file_name):
            view = document.view
            self.apply_view_changes(view, changes)
            view.run_command("save")
        else:
            FileUpdater(file_name).apply(changes)

    @staticmethod
    def apply_view_changes(view: sublime.View, text_changes: List[TextChange]):
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


class FileUpdater:
    def __init__(self, file_name: PathStr) -> None:
        self.path = Path(file_name)

    def apply(self, changes: List[TextChange]) -> None:
        try:
            old_text = self.path.read_text()
        except FileNotFoundError:
            old_text = ""

        new_text = self._update_text(old_text, changes)
        self.path.write_text(new_text)

    def _get_offset(self, lines: List[str], row: int, column: int) -> int:
        line_offset = sum([len(l) for l in lines[:row]])
        return line_offset + column

    def _update_text(self, source: str, changes: List[TextChange]) -> str:
        temp = source

        for change in changes:
            lines = temp.splitlines(keepends=True)
            start_offset = self._get_offset(lines, *change.start)
            end_offset = self._get_offset(lines, *change.end)

            temp = f"{temp[:start_offset]}{change.text}{temp[end_offset:]}"

        return temp
