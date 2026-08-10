import threading
from typing import List, Optional
import sublime
import sublime_plugin

from .plugin_base import PluginBase


class _StartServerCommand(PluginBase, sublime_plugin.TextCommand):

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
                self.client.server_process.run(command, envs)
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


class _TerminateServerCommand(PluginBase, sublime_plugin.TextCommand):

    def run(self, edit: sublime.Edit):
        self.client.disconnect()

    def is_visible(self):
        if not self.client:
            return False
        return self.client.is_ready()
