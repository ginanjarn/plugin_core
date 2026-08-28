import sublime
import sublime_plugin

from .plugin_base import (
    PluginBase,
    client_must_ready,
    must_valid_document,
)
from .initializer_mixin import InitializerMixin


class _InitializeCommand(PluginBase, sublime_plugin.TextCommand):

    client: InitializerMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit):
        self.client.initialize(self.view)
