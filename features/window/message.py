import sublime
from ...lsprotocol.client import Client, LogMessageParams, ShowMessageParams


class WindowMessageMixins(Client):

    def handle_log_message_notification(
        self, context: dict, params: LogMessageParams
    ) -> None:
        print(params["message"])

    def handle_show_message_notification(
        self, context: dict, params: ShowMessageParams
    ) -> None:
        sublime.status_message(params["message"])
