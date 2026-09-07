from typing import List

import sublime

from ...client_internal import BaseClient
from ...document import Document, TextChange
from ...uri import path_to_uri
from ...lsprotocol.lsprotocol import TextDocumentContentChangePartial

# Threshold in bytes to avoid sending full document text blindly
FULL_TEXT_SIZE_THRESHOLD = 200_000


class DocumentSynchronizerMixin(BaseClient):
    """
    Robust document synchronization mixin.
    Handles didOpen, didSave, didClose and didChange notifications with
    defensive checks and version management.
    """

    def set_client_capabilities(self):
        self.session.client_capabilities["textDocument"].update(
            {
                "synchronization": {
                    "dynamicRegistration": False,
                    "willSave": False,
                    "willSaveWaitUntil": False,
                    "didSave": True,
                }
            }
        )

    def textdocument_didopen(self, view: sublime.View, *, reload: bool = False) -> None:
        try:
            capabilities = (
                self.session.server_capabilities.get("textDocumentSync", {}) or {}
            )
            if not capabilities.get("openClose", False):
                return

            if not (view and view.is_valid()):
                return

            # Ensure diagnostic UI is visible for this view
            self.session.diagnostic_reporter.show(view)

            # If document already tracked and reload not requested, do nothing
            existing = self.session.get_document(view)
            if existing and not reload:
                return

            # If reloading, close the older tracked document first
            if existing and reload:
                self.textdocument_didclose(view)

            document = Document(view)

            # If file is already opened in another view, do not send didOpen again
            other = self.session.get_document_with_name(view.file_name())
            if not other and view.file_name():
                # Avoid sending full text for very large files
                text_to_send = document.text
                if len(text_to_send.encode("utf-8")) > FULL_TEXT_SIZE_THRESHOLD:
                    sublime.status_message(
                        "LSP: File too large to send full text on open"
                    )
                    # fall back to not sending text or send a trimmed version
                    text_to_send = text_to_send[:FULL_TEXT_SIZE_THRESHOLD]

                self.did_open_text_document_notification(
                    {
                        "textDocument": {
                            "languageId": document.language_id,
                            "text": text_to_send,
                            "uri": path_to_uri(document.file_name),
                            "version": document.version,
                        }
                    }
                )

            # Always add document to session so untitled buffers are tracked locally
            self.session.add_document(document)
        except Exception:
            print("[LSP Sync] Error in didOpen")

    def textdocument_didsave(self, view: sublime.View) -> None:
        try:
            capabilities = (
                self.session.server_capabilities.get("textDocumentSync", {}) or {}
            )
            if not capabilities.get("save", False):
                return

            document = self.session.get_document(view)
            if document and view.file_name():
                self.did_save_text_document_notification(
                    {"textDocument": {"uri": path_to_uri(document.file_name)}}
                )
            else:
                # If the server expects save but document not tracked, open it first
                self.textdocument_didopen(view)
        except Exception:
            print("[LSP Sync] Error in didSave")

    def textdocument_didclose(self, view: sublime.View) -> None:
        try:
            capabilities = (
                self.session.server_capabilities.get("textDocumentSync", {}) or {}
            )
            if not capabilities.get("openClose", False):
                return

            # Remove diagnostics for this view
            self.session.diagnostic_reporter.delete(view)

            # If the same file is open in multiple views, only remove local view tracking
            documents = self.session.get_documents(
                filter_func=lambda doc: doc.file_name == view.file_name()
            )
            if len(documents) > 1:
                self.session.remove_document(view)
                return

            document = self.session.get_document(view)
            if document and document.file_name:
                self.did_close_text_document_notification(
                    {"textDocument": {"uri": path_to_uri(document.file_name)}}
                )

            self.session.remove_document(view)
        except Exception:
            print("[LSP Sync] Error in didClose")

    def textdocument_didchange(
        self, view: sublime.View, changes: List[TextChange]
    ) -> None:
        try:
            capabilities = (
                self.session.server_capabilities.get("textDocumentSync", {}) or {}
            )
            change_mode = capabilities.get("change", 0)
            if not change_mode:
                return

            document = self.session.get_document(view)
            if not document:
                # If not tracked, open it first then send change
                self.textdocument_didopen(view)
                document = self.session.get_document(view)
                if not document:
                    return

            # Build contentChanges according to server's supported mode
            if change_mode == 1:
                # Full text sync
                full_text = view.substr(sublime.Region(0, view.size()))
                # Guard against huge payloads
                if len(full_text.encode("utf-8")) > FULL_TEXT_SIZE_THRESHOLD:
                    sublime.status_message("LSP: Skipping full text sync due to size")
                    return
                content_changes = {"text": full_text}
            elif change_mode == 2:
                # Incremental sync expects a list of TextDocumentContentChangePartial
                content_changes = [self._textchange_to_rpc(c) for c in changes if c]
                # If conversion produced no valid changes, skip
                if not content_changes:
                    return
            else:
                # Unknown mode, do nothing
                return

            self.did_change_text_document_notification(
                {
                    "textDocument": {
                        "uri": path_to_uri(document.file_name),
                        "version": document.version,
                    },
                    "contentChanges": content_changes,
                }
            )
        except Exception:
            print("[LSP Sync] Error in didChange")

    @staticmethod
    def _textchange_to_rpc(change: TextChange) -> TextDocumentContentChangePartial:
        """
        Convert internal TextChange to LSP TextDocumentContentChangePartial.
        Validate ranges and provide safe defaults on malformed input.
        """
        try:
            start, end = change.start, change.end
            # Ensure numeric indices
            start_line = int(start[0])
            start_char = int(start[1])
            end_line = int(end[0])
            end_char = int(end[1])
            return {
                "range": {
                    "start": {"line": start_line, "character": start_char},
                    "end": {"line": end_line, "character": end_char},
                },
                "rangeLength": int(getattr(change, "length", 0)),
                "text": getattr(change, "text", ""),
            }
        except Exception:
            # Fallback to sending the whole text if conversion fails
            return {"text": ""}
