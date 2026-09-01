from collections import namedtuple
from dataclasses import asdict
from pathlib import Path
from typing import List, Dict, Union

import sublime

from ..document import TextChange
from ..session import Session
from ..uri import uri_to_path
from ..lsprotocol.lsprotocol import (
    WorkspaceEdit,
    TextEdit,
    DocumentUri,
    TextDocumentEdit,
    CreateFile,
    RenameFile,
    DeleteFile,
)
from ...constant import COMMAND_PREFIX

LineCharacter = namedtuple("LineCharacter", ["line", "character"])
PathStr = str


class WorkspaceUpdater:
    """Workspace Updater"""

    def __init__(self, session: Session):
        self.session = session

    def apply(self, edit: WorkspaceEdit):
        if changes := edit.get("changes"):
            self._apply_changes(changes)
        if document_changes := edit.get("documentChanges"):
            self.apply_document_changes(document_changes)

    def _apply_changes(self, changes: Dict[DocumentUri, List[TextEdit]]):
        for uri, text_edits in changes.items():
            self.apply_text_edits(uri_to_path(uri), text_edits)

    def apply_document_changes(
        self, changes: List[Union[TextDocumentEdit, CreateFile, RenameFile, DeleteFile]]
    ):
        for change in changes:
            if "kind" in change:
                # CreateFile | RenameFile | DeleteFile
                self._apply_resource_change(change)
            else:
                # TextDocumentEdit
                self._apply_text_document_edit(change)

    def _apply_resource_change(self, resource_changes: dict) -> None:
        resource_change_map = {
            "create": self._create_file,
            "rename": self._rename_file,
            "delete": self._delete_file,
        }
        kind = resource_changes["kind"]
        resource_change_map[kind](resource_changes)

    def _apply_text_document_edit(self, text_document_edit: TextDocumentEdit):
        file_name = uri_to_path(text_document_edit["textDocument"]["uri"])
        edits = text_document_edit["edits"]
        self.apply_text_edits(file_name, edits)

    def apply_text_edits(self, file_name: str, edits: List[TextEdit]):
        text_changes = [rpc_to_textchange(c) for c in edits]
        if document := self.session.get_document_with_name(file_name):
            view = document.view
            self._apply_view_changes(view, text_changes)
            view.run_command("save")
        else:
            TextFile(file_name).apply_text_changes(text_changes)

    @staticmethod
    def _apply_view_changes(view: sublime.View, text_changes: List[TextChange]):
        view.run_command(
            COMMAND_PREFIX,
            {
                "action": "apply_text_change",
                "changes": [asdict(c) for c in text_changes],
            },
        )

    @staticmethod
    def _create_file(resource_changes: CreateFile):
        file_name = uri_to_path(resource_changes["textDocument"]["uri"])
        Path(file_name).touch(exist_ok=True)

    @staticmethod
    def _rename_file(resource_changes: RenameFile):
        old = uri_to_path(resource_changes["oldUri"])
        new = uri_to_path(resource_changes["newUri"])
        Path(old).rename(new)

        # retarget buffer to new path
        for view in [
            v for v in sublime.active_window().views() if v.file_name() == old
        ]:
            view.retarget(new)

    @staticmethod
    def _delete_file(resource_changes: DeleteFile):
        file_name = uri_to_path(resource_changes["textDocument"]["uri"])
        Path(file_name).unlink()

        # close opened view
        for view in [
            v for v in sublime.active_window().views() if v.file_name() == file_name
        ]:
            view.close()


def apply_workspace_edit(session: Session, edit: WorkspaceEdit) -> None:
    """apply workspace_edit"""
    WorkspaceUpdater(session).apply(edit)


def apply_text_edits(session: Session, file_name: str, edits: List[TextEdit]) -> None:
    """apply text_edits"""
    WorkspaceUpdater(session).apply_text_edits(file_name, edits)


def rpc_to_textchange(change: TextEdit) -> TextChange:
    """"""
    return TextChange(
        LineCharacter(**change["range"]["start"]),
        LineCharacter(**change["range"]["end"]),
        change["newText"],
        change.get("rangeLength"),
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

    def _apply_text_changes(self, source: str, text_changes: List[TextChange]) -> str:
        line_end = "\n"
        lines = source.split(line_end)

        # Apply text_changes from last to begin to ensure text changes don't
        # break change location
        for change in reversed(text_changes):
            srow, scol = change.start
            erow, ecol = change.end

            insert = lines[srow][:scol] + change.text + lines[erow][ecol:]
            lines = lines[:srow] + [insert] + lines[erow + 1 :]

        return line_end.join(lines)
