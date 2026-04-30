import sublime
from ...client_internal import BaseClient
from ...utils import on_main_thread
from ...lsprotocol.client import LogMessageParams, ShowMessageParams


class WindowMessageMixins(BaseClient):

    @on_main_thread
    def handle_log_message_notification(
        self, context: dict, params: LogMessageParams
    ) -> None:
        print(params["message"])

    @on_main_thread
    def handle_show_message_notification(
        self, context: dict, params: ShowMessageParams
    ) -> None:
        sublime.status_message(params["message"])
