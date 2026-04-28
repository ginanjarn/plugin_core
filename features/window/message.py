import sublime
from ...client_internal import BaseClient
from ...lsprotocol.client import LogMessageParams, ShowMessageParams


class WindowMessageMixins(BaseClient):

    def handle_log_message_notification(
        self, context: dict, params: LogMessageParams
    ) -> None:
        print(params["message"])

    def handle_show_message_notification(
        self, context: dict, params: ShowMessageParams
    ) -> None:
        sublime.status_message(params["message"])
