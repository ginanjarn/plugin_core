from typng import List

import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from .code_action_mixin import DocumentCodeActionMixin


class _CodeActionCommand(PluginBase, sublime_plugin.TextCommand):
    client: DocumentCodeActionMixin

    @client_must_ready
    @must_valid_document
    def run(self, edit: sublime.Edit, kinds: List[str] = None):
        self.client.textdocument_codeaction(self.view, self.view.sel()[0], kinds)

    def is_visible(self):
        return is_valid_document(self.view)
