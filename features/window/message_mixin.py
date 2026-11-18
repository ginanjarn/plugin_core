from typing import Any, Dict, List, Optional

import sublime

from ...lsprotocol.client import LogMessageParams, ShowMessageParams
from ...utils import on_main_thread
from ..base_feature import BaseFeature

# LSP MessageType: 1 = Error, 2 = Warning, 3 = Info, 4 = Log
_MESSAGE_TYPE_NAME = {
    1: "ERROR",
    2: "WARNING",
    3: "INFO",
    4: "LOG",
}


class WindowMessageMixin(BaseFeature):
    """Handle LSP window messages and show them in Sublime with sensible UI mapping."""

    def set_client_capabilities(self):
        super().set_client_capabilities()
        self.session.client_capabilities["window"].update(
            {
                "showMessage": {
                    "messageActionItem": {"additionalPropertiesSupport": False}
                }
            }
        )

    @on_main_thread
    def handle_log_message_notification(
        self, context: Dict[str, Any], params: LogMessageParams
    ) -> None:
        """Print server log messages to console with severity label."""
        try:
            msg_type = params.get("type", 4)
            text = params.get("message", "")
            label = _MESSAGE_TYPE_NAME.get(msg_type, "LOG")
            # Print to console for persistent debugging
            print(f"[LSP {label}] {text}")
        except Exception as e:
            print(f"[LSP LogMessage] Failed to handle log message: {e}")

    @on_main_thread
    def handle_show_message_notification(
        self, context: Dict[str, Any], params: ShowMessageParams
    ) -> None:
        """
        Show messages to the user. If actions are provided, present them in a quick panel.
        Uses different Sublime UI calls depending on severity.
        """
        try:
            msg_type = params.get("type", 3)
            text = params.get("message", "")
            actions: Optional[List[Dict[str, Any]]] = params.get("actions")

            # Console log for traceability
            label = _MESSAGE_TYPE_NAME.get(msg_type, "INFO")
            print(f"[LSP {label}] {text}")

            # Choose UI based on severity
            if msg_type == 1:
                # Error
                sublime.error_message(text)
            elif msg_type == 2:
                # Warning
                sublime.message_dialog(f"Warning: {text}")
            elif msg_type == 3:
                # Info
                sublime.message_dialog(text)
            else:
                # Log or unknown
                sublime.status_message(text)

            # If actions are present, let the user pick one and log the selection
            if actions:
                # Build display list for quick panel
                items = [a.get("title", str(a)) for a in actions]

                def on_done(index: int) -> None:
                    if index < 0:
                        print("[LSP ShowMessage] Action selection cancelled")
                        return
                    chosen = actions[index]
                    print(f"[LSP ShowMessage] Action chosen: {chosen.get('title')}")
                    # If you want to send a response back to the server for message requests,
                    # implement the corresponding request/response call here.

                # Show quick panel on main thread
                window = sublime.active_window()
                if window:
                    window.show_quick_panel(items, on_done)
        except Exception as e:
            print(f"[LSP ShowMessage] Failed to display message: {e}")
