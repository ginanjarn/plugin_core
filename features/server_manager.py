import threading
from typing import List, Optional
import sublime
import sublime_plugin

from ..client import Client


class _StartServerCommand(sublime_plugin.TextCommand):

    client: Client = None
    _run_lock = threading.Lock()

    def run(
        self,
        edit: sublime.Edit,
        command: Optional[List[str]] = None,
        envs: Optional[dict] = None,
    ):
        thread = threading.Thread(target=self.run_task, args=(command, envs))
        thread.start()

    def run_task(
        self,
        command: Optional[List[str]] = None,
        envs: Optional[dict] = None,
    ):
        if self._run_lock.locked():
            return

        with self._run_lock:
            try:
                self.client.start_server(command, envs)
                self.client.connect()

                self.client.initialize(self.view)
                self.client.wait_initialized()

                self.client.textdocument_didopen(self.view)

            except Exception as err:
                print("start server error:", err)

    def is_visible(self):
        if not self.client:
            return False
        return not self.client.is_ready()


class _TerminateServerCommand(sublime_plugin.TextCommand):

    client: Client = None

    def run(self, edit: sublime.Edit):
        self.client.disconnect()

    def is_visible(self):
        if not self.client:
            return False
        return self.client.is_ready()
