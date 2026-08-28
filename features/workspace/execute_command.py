import sublime_plugin

from ..plugin_base import client_must_ready
from .execute_command_mixin import WorkspaceExecuteCommandMixin


class _WorkspaceExecuteCommandCommand(sublime_plugin.WindowCommand):
    client: WorkspaceExecuteCommandMixin

    @client_must_ready
    def run(self, command: dict):
        self.client.workspace_executecommand(command)

    def is_visible(self):
        return self.client and self.client.is_ready()
