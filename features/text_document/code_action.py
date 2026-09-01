from typing import List

import sublime

from .code_action_mixin import DocumentCodeActionMixin


class _DocumentCodeActionCommandMixin:
    client: DocumentCodeActionMixin

    def run(self, edit: sublime.Edit, kinds: List[str] = None):
        self.client.textdocument_codeaction(self.view, self.view.sel()[0], kinds)
