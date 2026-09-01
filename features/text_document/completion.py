from typing import List, Optional

import sublime

from .completion_mixin import DocumentCompletionMixin


class DocumentCompletionEventMixin:
    """Event listener to trigger and manage completions."""

    client: DocumentCompletionMixin

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prev_trigger_location = 0

    def on_query_completions(
        self, prefix: str, locations: List[int]
    ) -> Optional[sublime.CompletionList]:
        location = min(locations)

        if self.client.is_completions_available():
            items = self.client.pop_completions()
            if (not items) or self._is_context_changed(
                self.view, self.prev_trigger_location, location
            ):
                self.hide_completions(self.view)
                return None
            return sublime.CompletionList(items, flags=sublime.INHIBIT_WORD_COMPLETIONS)

        self.prev_trigger_location = location
        row, col = self.view.rowcol(location)
        self.client.textdocument_completion(self.view, row, col)
        self.hide_completions(self.view)
        return None

    def _is_context_changed(self, view: sublime.View, old: int, new: int) -> bool:
        """Check if completion context has changed."""
        if old == new:
            return False
        word = view.word(old)
        return not (new in word and view.substr(word).isidentifier())

    def hide_completions(self, view: sublime.View) -> None:
        view.run_command("hide_auto_complete")
