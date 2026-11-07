import threading
from locale import getlocale
from os import getpid
from pathlib import Path
from uuid import uuid4

import sublime

from ..base_client import BaseClient
from ..lsprotocol.client import InitializeResult
from ..session import SessionStatus, Workspace
from ..uri import path_to_uri


class InitializerMixin(BaseClient):

    _initialized_event = threading.Event()

    def initialize(self, view: sublime.View):
        if self.session.status in {
            SessionStatus.Initializing,
            SessionStatus.Initialized,
        }:
            return
        self.session.status = SessionStatus.Initializing

        # Check view is exist and has file_name
        if not (view or view.file_name()):
            return

        workspace_path = get_workspace_path(view)
        if not workspace_path:
            return

        self._initialized_event.clear()

        self.session.workspace_folders = [Workspace(workspace_path)]
        params = {
            "processId": getpid(),
            "clientInfo": {"name": "Sublime Text", "version": sublime.version()},
            "locale": getlocale()[0],
            "rootPath": workspace_path,
            "rootUri": path_to_uri(workspace_path),
            "capabilities": self.session.client_capabilities,
            "initializationOptions": {},
            "trace": "on",
            "workDoneToken": int(uuid4()),
            "workspaceFolders": [
                {"uri": path_to_uri(w.rootPath), "name": str(w.rootPath)}
                for w in self.session.workspace_folders
            ],
        }
        self.initialize_request(params)

    def handle_initialize_result(self, context: dict, result: InitializeResult) -> None:
        self.session.server_capabilities = result["capabilities"]
        self.initialized()

    def initialized(self):
        self.initialized_notification({})
        self.session.status = SessionStatus.Initialized
        self._initialized_event.set()

    def wait_initialized(self, timeout: float = 10.0) -> None:
        if not self._initialized_event.wait(timeout):
            self.session.status = SessionStatus.NotSet
            raise TimeoutError("Initialize timed out")


def get_workspace_path(view: sublime.View, return_parent: bool = True) -> str:
    """Get workspace path for view.

    Params:
        view: View
            target
        return_parent: bool
            if True, return parent folder if view not opened in 'Window folders'

    Returns:
        workspace path or empty string
    """
    file_name = view.file_name()
    if folders := [
        folder for folder in view.window().folders() if file_name.startswith(folder)
    ]:
        # File is opened in multiple folder
        return max(folders)

    if not return_parent:
        return ""

    return str(Path(file_name).parent)
