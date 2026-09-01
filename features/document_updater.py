from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import sublime

from ..document import TextChange


@dataclass
class _BufferedTextChange:
    region: sublime.Region
    old_text: str
    new_text: str

    __slots__ = ("region", "old_text", "new_text")


class _ApplyTextChangesCommandMixin:
    """
    Apply text changes serialized from TextChange.

    Usage:
      view.run_command("_apply_text_changes", {"changes": [...], "dry_run": False})
    """

    def run(
        self, edit: sublime.Edit, changes: List[Dict[str, Any]], dry_run: bool = False
    ) -> None:
        try:
            text_changes = []
            for c in changes:
                tc = self.to_text_change_safe(c)
                if tc:
                    text_changes.append(tc)

            if not text_changes:
                sublime.status_message("No valid text changes to apply")
                return

            # Optionally show a preview without applying
            if dry_run:
                sublime.status_message(
                    f"LSP: Dry run - {len(text_changes)} changes validated"
                )
                return

            # Preserve selections and viewport
            prev_sel = list(self.view.sel())
            prev_visible = self.view.visible_region()

            self.apply(edit, text_changes)

            # Restore selections and viewport if possible
            try:
                self.view.sel().clear()
                self.view.sel().add_all(prev_sel)
                self.view.show(prev_visible)
            except Exception:
                # best-effort restore; ignore failures
                pass

            sublime.status_message(f"LSP: Applied {len(text_changes)} text changes")
        except Exception as e:
            print(f"[LSP ApplyTextChanges] Error applying changes: {e}")

    def apply(
        self, edit: sublime.Edit, text_changes: List[_BufferedTextChange]
    ) -> None:
        """
        Apply buffered changes from last to first so earlier edits don't shift later ranges.
        Regions are validated and clamped to the current buffer size.
        """
        # Sort by region.begin() descending to ensure safe application
        sorted_changes = sorted(
            text_changes, key=lambda t: t.region.begin(), reverse=True
        )

        for change in sorted_changes:
            # Validate region bounds
            region = self._clamp_region(change.region)
            try:
                self.view.replace(edit, region, change.new_text)
            except Exception as e:
                print(f"[LSP ApplyTextChanges] Failed to replace region {region}: {e}")

    def to_text_change_safe(
        self, change: Dict[str, Any]
    ) -> Optional[_BufferedTextChange]:
        """
        Convert a serialized TextChange dict to _BufferedTextChange safely.
        Expected dict shape matches TextChange dataclass: start, end, text, length (optional).
        Returns None on malformed input.
        """
        try:
            # Accept either a dict that can be unpacked into TextChange or already a TextChange-like
            if isinstance(change, TextChange):
                tc = change
            elif isinstance(change, dict):
                # Defensive extraction with defaults
                start = tuple(change.get("start", (0, 0)))
                end = tuple(change.get("end", (0, 0)))
                text = change.get("text", "")
                length = change.get("length", None)
                tc = TextChange(start, end, text, length)
            else:
                return None

            # Convert to sublime.Region using view.text_point, clamp to buffer size
            text_point = self.view.text_point
            try:
                a = text_point(int(tc.start[0]), int(tc.start[1]))
                b = text_point(int(tc.end[0]), int(tc.end[1]))
            except Exception:
                # fallback: treat as empty region at 0
                a, b = 0, 0

            region = sublime.Region(min(a, b), max(a, b))
            region = self._clamp_region(region)

            old_text = self.view.substr(region)
            return _BufferedTextChange(
                region=region, old_text=old_text, new_text=str(tc.text)
            )
        except Exception as e:
            print(f"[LSP ApplyTextChanges] Malformed change entry skipped: {e}")
            return None

    def _clamp_region(self, region: sublime.Region) -> sublime.Region:
        """
        Ensure region is within buffer bounds. If region is empty and at EOF, extend safely.
        """
        size = self.view.size()
        a = max(0, min(region.a, size))
        b = max(0, min(region.b, size))
        if a == b and a == size:
            # If region is at EOF and empty, keep as-is (insertion at EOF)
            return sublime.Region(a, b)
        return sublime.Region(a, b)
