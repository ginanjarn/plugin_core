import sublime

from .initializer_mixin import InitializerMixin


class _InitializeCommandMixin:

    client: InitializerMixin

    def initialize(self, edit: sublime.Edit):
        self.client.initialize(self.view)
