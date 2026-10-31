from typing import Set

import sublime

from .signature_help_mixin import DocumentSignatureHelpMixin


class _DocumentSignatureHelpCommandMixin:
    client: DocumentSignatureHelpMixin

    def document_signature_help(self, edit: sublime.Edit) -> None:
        self.client.textdocument_signaturehelp(self.view)


class DocumentSignatureHelpEventMixin:
    """
    Trigger signature help on typing trigger characters and hide popup on cursor movement.
    Uses server-provided triggerCharacters when available.
    """

    client: DocumentSignatureHelpMixin
    _signature_trigger_characters: Set[str]
    insert_commands = frozenset({"insert", "insert_snippet", "insert_completion"})

    def document_signature_help(self) -> None:
        # Only react to insert-like commands to avoid triggering on non-insert edits
        name, *_ = self.view.command_history(0)
        if name not in self.insert_commands:
            return

        # get the character just inserted
        point = self.view.sel()[0].begin()
        if point == 0:
            return
        char = self.view.substr(point - 1)
        if char in self.signature_trigger_characters:
            self.client.textdocument_signaturehelp(self.view)

    @property
    def signature_trigger_characters(self) -> Set[str]:
        if getattr(self, "_signature_trigger_characters", None):
            return self._signature_trigger_characters

        try:
            capabilities = self.client.session.server_capabilities
            chars = capabilities["signatureHelpProvider"]["triggerCharacters"]
        except Exception:
            chars = ["("]

        self._signature_trigger_characters = set(chars)
        return self._signature_trigger_characters
