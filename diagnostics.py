"""diagnostics object"""

import threading
from collections import namedtuple, defaultdict
from dataclasses import dataclass, asdict
from itertools import chain
from pathlib import Path
from typing import Dict, List, Set, Callable

import sublime

from ..constant import PACKAGE_NAME, COMMAND_PREFIX
from .document import TextChange

PathStr = str
LineCharacter = namedtuple("LineCharacter", ["line", "character"])


@dataclass
class DiagnosticItem:
    severity: int
    region: sublime.Region
    message: str

    __slots__ = ("severity", "region", "message")

    @classmethod
    def from_rpc(cls, view: sublime.View, diagnostic: dict, /):
        """"""
        start = LineCharacter(**diagnostic["range"]["start"])
        end = LineCharacter(**diagnostic["range"]["end"])
        region = sublime.Region(view.text_point(*start), view.text_point(*end))
        message = diagnostic["message"]
        if source := diagnostic.get("source"):
            message = f"{message} ({source})"
        # resolve highlight region if start == end
        if region.empty():
            region.a -= 1

        return cls(diagnostic["severity"], region, message)


@dataclass
class ReportSettings:
    highlight_text: bool = True
    show_status: bool = True
    show_panel: bool = False


class PubSub:
    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[Callable[..., None]]] = dict()

    def subscribe(self, subject: str, callback: Callable[..., None]):
        try:
            self._subscribers[subject].add(callback)
        except KeyError:
            self._subscribers[subject] = {callback}

    def publish(self, subject: str, *args, **kwargs) -> None:
        for callback in self._subscribers.get(subject, []):
            callback(*args, **kwargs)


class DiagnosticManager:
    """"""

    PUBLISH_KEY = "publish_diagnostic"
    CLEAR_KEY = "clear_diagnostic"

    def __init__(self, settings: ReportSettings = None) -> None:
        # One file may be openend in many View. For efficiency reason,
        # only show report such text highlight on active view.

        # Store raw diagnostic items to use later in CodeAction.
        self.raw_itams_map: Dict[PathStr, List[dict]] = defaultdict(list)
        self.items_map: Dict[PathStr, List[DiagnosticItem]] = defaultdict(list)

        self.report_publisher = PubSub()
        self.register_reporter(settings)

        self._change_lock = threading.Lock()
        self._active_view: sublime.View = None

    def register_reporter(self, settings: ReportSettings = None):
        settings = settings or ReportSettings()

        if settings.highlight_text:
            key = f"{PACKAGE_NAME}_DIAGNOSTIC_REGIONS"
            highlighter = SyntaxHighlighter(key)
            self.report_publisher.subscribe(
                self.PUBLISH_KEY, highlighter.highlight_text
            )
            self.report_publisher.subscribe(self.CLEAR_KEY, highlighter.clear)

        if settings.show_status:
            key = f"{PACKAGE_NAME}_DIAGNOSTIC_STATUS"
            status_reporter = StatusReporter(key)
            self.report_publisher.subscribe(
                self.PUBLISH_KEY, status_reporter.show_status
            )
            self.report_publisher.subscribe(self.CLEAR_KEY, status_reporter.clear)

        if settings.show_panel:
            panel = OutputPanelReporter(PACKAGE_NAME)
            self.report_publisher.subscribe(self.PUBLISH_KEY, panel.show_panel)
            self.report_publisher.subscribe(self.CLEAR_KEY, panel.destroy)

    def reset(self):
        self.report_publisher.publish(self.CLEAR_KEY)

        self._active_view = None
        self.raw_itams_map.clear()
        self.items_map.clear()

    def get_raw(self, view: sublime.View) -> List[dict]:
        """return raw dict of diagnostic items"""
        with self._change_lock:
            return self.raw_itams_map[view.file_name()]

    def get(self, view: sublime.View) -> List[DiagnosticItem]:
        """return diagnostic item"""
        with self._change_lock:
            return self.items_map[view.file_name()]

    def add(self, view: sublime.View, diagnostics: List[dict]):
        """add diagnostics"""
        with self._change_lock:
            self.raw_itams_map[view.file_name()] = diagnostics
            self.items_map[view.file_name()] = [
                DiagnosticItem.from_rpc(view, d) for d in diagnostics
            ]
            self._show_report(view)

    def remove(self, view: sublime.View):
        """remove diagnostics"""
        with self._change_lock:
            try:
                del self.raw_itams_map[view.file_name()]
                del self.items_map[view.file_name()]
            except KeyError:
                pass
            self._show_report(view)

    def set_active_view(self, view: sublime.View):
        """set active view"""
        if view == self._active_view:
            # active view not changed
            return

        with self._change_lock:
            self._active_view = view
            self._show_report(view)

    def _show_report(self, view: sublime.View):
        if view != self._active_view:
            # cancel show report
            return

        diagnostic_items = self.items_map[view.file_name()]
        self.report_publisher.publish(self.PUBLISH_KEY, view, diagnostic_items)


class SyntaxHighlighter:
    def __init__(self, region_key: str) -> None:
        self._region_key = region_key

    def highlight_text(
        self, view: sublime.View, diagnostic_items: List[DiagnosticItem]
    ):
        regions = [item.region for item in diagnostic_items]
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


class StatusReporter:
    def __init__(self, status_key: str) -> None:
        self._status_key = status_key

    def show_status(self, view: sublime.View, diagnostic_items: List[DiagnosticItem]):
        err_count = len([item for item in diagnostic_items if item.severity == 1])
        warn_count = len([item for item in diagnostic_items if item.severity == 2])
        view.set_status(self._status_key, f"Errors {err_count}, Warnings {warn_count}")

    def clear(self):
        for view in chain.from_iterable([w.views() for w in sublime.windows()]):
            view.erase_status(self._status_key)


class OutputPanelReporter:
    def __init__(self, panel_name: str) -> None:
        self._panel = OutputPanel(panel_name)

    def show_panel(
        self,
        view: sublime.View,
        diagnostic_items: List[DiagnosticItem],
    ):
        def build_line(view: sublime.View, item: DiagnosticItem):
            short_name = Path(view.file_name()).name
            row, col = view.rowcol(item.region.begin())
            return f"{short_name}:{row+1}:{col} {item.message}"

        content = "\n".join([build_line(view, item) for item in diagnostic_items])
        self._panel.set_content(content)
        self._panel.show()

    def destroy(self):
        self._panel.destroy()


class OutputPanel:
    SETTINGS = {"gutter": False, "word_wrap": False}

    def __init__(self, panel_name: str):
        self.panel_name = panel_name
        self.panel: sublime.View = None

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
