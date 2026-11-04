import threading

import sublime

from ..base_client import BaseClient
from ..child_process import ProcessArgs


class _StartServerCommandMixin:
    client: BaseClient
    _run_lock = threading.Lock()

    def start_server(self, edit: sublime.Edit, process_args: dict):
        thread = threading.Thread(target=self.run_task, args=(process_args,))
        thread.start()

    def run_task(self, args: dict):
        if self._run_lock.locked():
            return

        with self._run_lock:
            try:
                self.client.server_process.run(ProcessArgs(**args))
                self.client.connect()

                self.client.initialize(self.view)
                self.client.wait_initialized()

                self.client.textdocument_didopen(self.view)

            except Exception as err:
                print("start server error:", err)


class _TerminateServerCommandMixin:
    client: BaseClient

    def terminate_server(self, edit: sublime.Edit):
        self.client.shutdown()
