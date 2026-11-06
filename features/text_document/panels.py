"""panels"""

from dataclasses import asdict

import sublime
from sublime import View

from ...document import TextChange
from ...registry import COMMAND_NAME


class OutputPanel:

    _settings = {"gutter": False, "word_wrap": False}

    def __init__(self, panel_name: str):
        self.panel_name = panel_name
        self.panel: View = None

    def _create_panel(self):
        self.panel = sublime.active_window().create_output_panel(self.panel_name)
        self.panel.settings().update(self._settings)
        self.panel.set_read_only(False)

    def set_text(self, text: str):
        if not (self.panel and self.panel.is_valid()):
            self._create_panel()

        start = (0, 0)
        end = self.panel.rowcol(self.panel.size())

        change = TextChange(start, end, text, None)
        self.panel.run_command(
            COMMAND_NAME,
            {
                "action": "apply_text_change",
                "changes": [asdict(change)],
            },
        )

    def insert_text(self, text: str) -> None:
        if not (self.panel and self.panel.is_valid()):
            self._create_panel()

        self.panel.run_command("insert", {"characters": text})

    def show(self) -> None:
        """show output panel"""
        if not self.panel:
            return
        self.panel.window().run_command(
            "show_panel", {"panel": f"output.{self.panel_name}"}
        )

    def destroy(self):
        """destroy output panel"""
        if not self.panel:
            return
        self.panel.window().destroy_output_panel(self.panel_name)
