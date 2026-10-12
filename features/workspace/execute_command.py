from typing import Dict, Any

import sublime

from .execute_command_mixin import WorkspaceExecuteCommandMixin


class _WorkspaceExecuteCommandCommandMixin:
    """Workspace execute command"""

    client: WorkspaceExecuteCommandMixin

    def run(self, edit: sublime.Edit, command: Dict[str, Any]) -> None:
        self.client.workspace_executecommand(command)
