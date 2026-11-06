from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Set

import sublime
from sublime import View

from .panels import OutputPanel


@dataclass
class Diagnostic:
    severity: int
    region: sublime.Region
    message: str

    __slots__ = ("severity", "region", "message")


@dataclass
class Settings:
    highlight_text: bool = True
    status_message: bool = True
    report_panel: bool = False


class ReportManager:
    """"""

    PUBLISH_KEY = "publish_diagnostic"
    CLEAR_KEY = "clear_diagnostic"

    def __init__(self, manager_id: str, settings: Settings) -> None:
        self._diagnostics_map: Dict[View, List[Diagnostic]] = defaultdict(list)
        self._active_view: View = None

        # reporter publisher
        self.report_publisher = Publisher()

        key = f"{manager_id}_DIAGNOSTIC"
        self.highlight_text = HighlightText(key)
        self.status_message = StatusMessage(key)
        self.report_panel = ReportPanel(manager_id)

        self.update_reporter(settings)

    def update_reporter(self, settings: Settings):
        # clear existing report
        self.report_publisher.publish(self.CLEAR_KEY)

        reporters = []
        if settings.highlight_text:
            reporters.append(self.highlight_text)
        if settings.status_message:
            reporters.append(self.status_message)
        if settings.report_panel:
            reporters.append(self.report_panel)

        self.report_publisher.clear_subscriber()
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
        try:
            del self._diagnostics_map[view]
        except KeyError:
            pass

    def show(self, view: View):
        self._show(view=view)

    def _show(self, *, view: View, force: bool = False):
        if view == self._active_view:
            if not force:
                return
        else:
            self._active_view = view

        diagnostic_items = self._diagnostics_map.get(view, [])
        self.report_publisher.publish(self.PUBLISH_KEY, view, diagnostic_items)


class Publisher:
    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[Callable[..., None]]] = defaultdict(set)

    def clear_subscriber(self) -> None:
        self._subscribers.clear()

    def subscribe(self, subject: str, callback: Callable[..., None]):
        self._subscribers[subject].add(callback)

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

    add_regions_args = {
        "scope": "string",
        "icon": "circle",
        "flags": sublime.DRAW_NO_FILL
        | sublime.DRAW_NO_OUTLINE
        | sublime.DRAW_SQUIGGLY_UNDERLINE,
    }

    def show(self, view: View, diagnostics: List[Diagnostic]):
        regions = [d.region for d in diagnostics]
        view.add_regions(
            key=self._region_key,
            regions=regions,
            **self.add_regions_args,
        )

    def clear(self):
        for window in sublime.windows():
            for view in window.views():
                view.erase_regions(self._region_key)


class StatusMessage(AbstractReporter):
    def __init__(self, status_key: str) -> None:
        self._status_key = status_key

    def show(self, view: View, diagnostics: List[Diagnostic]):
        err_count = len([d for d in diagnostics if d.severity == 1])
        warn_count = len(diagnostics) - err_count
        view.set_status(self._status_key, f"Errors {err_count}, Warnings {warn_count}")

    def clear(self):
        for window in sublime.windows():
            for view in window.views():
                view.erase_status(self._status_key)


class ReportPanel(AbstractReporter):
    def __init__(self, panel_name: str) -> None:
        self._panel = OutputPanel(panel_name)

    def show(self, view: View, diagnostics: List[Diagnostic]):
        content = "\n".join([self.build_line(view, d) for d in diagnostics])
        self._panel.set_text(content)
        self._panel.show()

    def build_line(self, view: View, item: Diagnostic):
        short_name = Path(view.file_name()).name
        row, col = view.rowcol(item.region.begin())
        return f"{short_name}:{row+1}:{col} {item.message}"

    def clear(self):
        self._panel.destroy()
