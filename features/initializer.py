import sublime

from .initializer_mixin import InitializerMixin


class _InitializeCommandMixin:

    client: InitializerMixin

    def run(self, edit: sublime.Edit):
        self.client.initialize(self.view)
