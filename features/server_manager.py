from typing import Optional
import sublime
import sublime_plugin

from ..client import Client


class _StartServerCommand(sublime_plugin.TextCommand):

    client: Client = None

    def run(self, edit: sublime.Edit, envs: Optional[dict] = None):
        self.client.start_server(envs)

    def is_visible(self):
        if not self.client:
            return False
        return not self.client.is_ready()


class _TerminateServerCommand(sublime_plugin.TextCommand):

    client: Client = None

    def run(self, edit: sublime.Edit):
        self.client.terminate()

    def is_visible(self):
        if not self.client:
            return False
        return self.client.is_server_running()
