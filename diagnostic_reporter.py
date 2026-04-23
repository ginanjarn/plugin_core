from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, asdict
from itertools import chain
from pathlib import Path
from typing import Dict, List, Set, Callable

import sublime
from sublime import View

from .document import TextChange
from ..constant import PACKAGE_NAME, COMMAND_PREFIX


@dataclass
class Diagnostic:
    severity: int
    region: sublime.Region
    message: str

    __slots__ = ("severity", "region", "message")


@dataclass
class Settings:
    highlight_text: bool = True
    show_status: bool = True
    show_panel: bool = False


class ReportManager:
    """"""

    PUBLISH_KEY = "publish_diagnostic"
    CLEAR_KEY = "clear_diagnostic"

    def __init__(self, settings: Settings = None) -> None:
        self.report_publisher = PubSub()
        self.register_reporter(settings)

        self._diagnostics_map: Dict[View, List[Diagnostic]] = defaultdict(list)
        self._active_view: View = None

    def register_reporter(self, settings: Settings = None):
        settings = settings or Settings()

        reporters = []
        key = f"{PACKAGE_NAME}_DIAGNOSTIC"
        if settings.highlight_text:
            reporters.append(HighlightText(key))
        if settings.show_status:
            reporters.append(StatusMessage(key))
        if settings.show_panel:
            reporters.append(DiagnosticPanel(PACKAGE_NAME))

        for r in reporters:
            self.report_publisher.subscribe(self.PUBLISH_KEY, r.show)
            self.report_publisher.subscribe(self.CLEAR_KEY, r.clear)

    def reset(self):
        self.report_publisher.publish(self.CLEAR_KEY)
        self._active_view = None
        self._diagnostics_map.clear()

    def report(self, view: View, diagnostics: List[Diagnostic]):
        """report diagnostics"""
        self._diagnostics_map[view] = diagnostics
        self._show(view=view, force=True)

    def delete(self, view: sublime.View):
        del self._diagnostics_map[view]

    def show(self, view: View):
        self._show(view=view)

    def _show(self, *, view: View, force: bool = False):
        if view == self._active_view:
            if not force:
                return
        else:
            self._active_view = view

        diagnostic_items = self._diagnostics_map[view]
        self.report_publisher.publish(self.PUBLISH_KEY, view, diagnostic_items)


class PubSub:
    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[Callable[..., None]]] = dict()

    def subscribe(self, subject: str, callback: Callable[..., None]):
        try:
            self._subscribers[subject].add(callback)
        except KeyError:
            self._subscribers[subject] = {callback}

    def publish(self, subject: str, *args, **kwargs) -> None:
        for callback in self._subscribers[subject]:
            callback(*args, **kwargs)


class AbstractReporter(ABC):

    @abstractmethod
    def show(self, view: View, diagnostics: List[Diagnostic]) -> None:
        """show report"""

    @abstractmethod
    def clear(self) -> None:
        """clear report"""


class HighlightText(AbstractReporter):
    def __init__(self, region_key: str) -> None:
        self._region_key = region_key

    def show(self, view: View, diagnostics: List[Diagnostic]):
        regions = [d.region for d in diagnostics]
        view.add_regions(
            key=self._region_key,
            regions=regions,
            scope="string",
            icon="circle",
            flags=sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            | sublime.DRAW_SQUIGGLY_UNDERLINE,
        )

    def clear(self):
        for view in chain.from_iterable([w.views() for w in sublime.windows()]):
            view.erase_regions(self._region_key)


class StatusMessage(AbstractReporter):
    def __init__(self, status_key: str) -> None:
        self._status_key = status_key

    def show(self, view: View, diagnostics: List[Diagnostic]):
        err_count = len([d for d in diagnostics if d.severity == 1])
        warn_count = len([d for d in diagnostics if d.severity == 2])
        view.set_status(self._status_key, f"Errors {err_count}, Warnings {warn_count}")

    def clear(self):
        for view in chain.from_iterable([w.views() for w in sublime.windows()]):
            view.erase_status(self._status_key)


class DiagnosticPanel(AbstractReporter):
    def __init__(self, panel_name: str) -> None:
        self._panel = OutputPanel(panel_name)

    def show(self, view: View, diagnostics: List[Diagnostic]):
        content = "\n".join([self.build_line(view, d) for d in diagnostics])
        self._panel.set_content(content)
        self._panel.show()

    def build_line(self, view: View, item: Diagnostic):
        short_name = Path(view.file_name()).name
        row, col = view.rowcol(item.region.begin())
        return f"{short_name}:{row+1}:{col} {item.message}"

    def clear(self):
        self._panel.destroy()


class OutputPanel:
    SETTINGS = {"gutter": False, "word_wrap": False}

    def __init__(self, panel_name: str):
        self.panel_name = panel_name
        self.panel: View = None

    def _create_panel(self):
        self.panel = sublime.active_window().create_output_panel(self.panel_name)
        self.panel.settings().update(self.SETTINGS)
        self.panel.set_read_only(False)

    def set_content(self, text: str):
        if not (self.panel and self.panel.is_valid()):
            self._create_panel()

        # clear selection in output panel
        self.panel.sel().clear()
        start = (0, 0)
        end = self.panel.rowcol(self.panel.size())

        change = TextChange(start, end, text, -1)
        self.panel.run_command(
            f"{COMMAND_PREFIX}_apply_text_changes",
            {"changes": [asdict(change)]},
        )

    def show(self) -> None:
        """show output panel"""
        sublime.active_window().run_command(
            "show_panel", {"panel": f"output.{self.panel_name}"}
        )

    def destroy(self):
        """destroy output panel"""
        for window in sublime.windows():
            window.destroy_output_panel(self.panel_name)
