import sublime


class WindowMessageMixins:

    def handle_window_logmessage(self, context: dict, params: dict):
        print(params["message"])

    def handle_window_showmessage(self, context: dict, params: dict):
        sublime.status_message(params["message"])
