from typing import List
import sublime
import sublime_plugin

from ..plugin_base import (
    PluginBase,
    client_must_ready,
    is_valid_document,
    must_valid_document,
)
from ...client_internal import BaseClient
from ...document import Document, TextChange
from ...uri import path_to_uri
from ...lsprotocol.lsprotocol import TextDocumentContentChangePartial


class DocumentSynchronizerMixins(BaseClient):

    def textdocument_didopen(self, view: sublime.View, *, reload: bool = False):
        capabilities = self.session.server_capabilities.get("textDocumentSync", {})
        if not capabilities.get("openClose", False):
            return

        # check if view not closed
        if not (view and view.is_valid()):
            return
        # show diagnostic report
        self.session.diagnostic_reporter.show(view)

        # Check if document has opened
        if self.session.get_document(view):
            if not reload:
                return

            # Close older document.
            self.textdocument_didclose(view)

        document = Document(view)

        # Check if the document has opened in other view
        other = self.session.get_document_with_name(view.file_name())
        if not other:
            # Notify server to open document
            self.did_open_text_document_notification(
                {
                    "textDocument": {
                        "languageId": document.language_id,
                        "text": document.text,
                        "uri": path_to_uri(document.file_name),
                        "version": document.version,
                    }
                },
            )

        # Add current document
        self.session.add_document(document)

    def textdocument_didsave(self, view: sublime.View):
        capabilities = self.session.server_capabilities.get("textDocumentSync", {})
        if not capabilities.get("save", False):
            return

        if document := self.session.get_document(view):
            self.did_save_text_document_notification(
                {"textDocument": {"uri": path_to_uri(document.file_name)}},
            )

        else:
            # untitled document not yet loaded to server
            self.textdocument_didopen(view)

    def textdocument_didclose(self, view: sublime.View):
        capabilities = self.session.server_capabilities.get("textDocumentSync", {})
        if not capabilities.get("openClose", False):
            return

        # delete diagnostic report
        self.session.diagnostic_reporter.delete(view)

        # Check if the document open in multiple view like side-by-side layout
        documents = self.session.get_documents(
            filter_func=lambda doc: doc.file_name == view.file_name()
        )
        if len(documents) > 1:
            # Remove the document but don't notify to server
            self.session.remove_document(view)
            return

        if document := self.session.get_document(view):
            self.did_close_text_document_notification(
                {"textDocument": {"uri": path_to_uri(document.file_name)}},
            )

        self.session.remove_document(view)

    def textdocument_didchange(self, view: sublime.View, changes: List[TextChange]):
        capabilities = self.session.server_capabilities.get("textDocumentSync", {})
        change_mode = capabilities.get("change", 0)
        if not change_mode:
            return

        if document := self.session.get_document(view):
            if change_mode == 1:
                contentChanges = {"text": view.substr(sublime.Region(0, view.size()))}
            elif change_mode == 2:
                contentChanges = [self._textchange_to_rpc(c) for c in changes]

            self.did_change_text_document_notification(
                {
                    "contentChanges": contentChanges,
                    "textDocument": {
                        "uri": path_to_uri(document.file_name),
                        "version": document.version,
                    },
                },
            )

    @staticmethod
    def _textchange_to_rpc(change: TextChange) -> TextDocumentContentChangePartial:
        """"""
        start, end = change.start, change.end
        return {
            "range": {
                "start": {"line": start[0], "character": start[1]},
                "end": {"line": end[0], "character": end[1]},
            },
            "rangeLength": change.length,
            "text": change.text,
        }


class SynchronizeEventAdapter(PluginBase):
    client: DocumentSynchronizerMixins

    def didopen(self, view: sublime.View, *, reload: bool = False):
        self.client.textdocument_didopen(view, reload=reload)

    def didsave(self, view: sublime.View):
        self.client.textdocument_didsave(view)

    def didclose(self, view: sublime.View):
        self.client.textdocument_didclose(view)

    def didchange(self, view: sublime.View, changes: List[TextChange]):
        self.client.textdocument_didchange(view, changes)


class DocumentSynchronizeEventListener(
    SynchronizeEventAdapter, sublime_plugin.ViewEventListener
):

    @client_must_ready
    @must_valid_document
    def on_activated_async(self):
        self.didopen(self.view)

    @client_must_ready
    @must_valid_document
    def on_load_async(self):
        self.didopen(self.view, reload=True)

    @client_must_ready
    @must_valid_document
    def on_reload_async(self):
        self.didopen(self.view, reload=True)

    @client_must_ready
    @must_valid_document
    def on_revert_async(self):
        self.didopen(self.view, reload=True)

    @client_must_ready
    @must_valid_document
    def on_post_save_async(self):
        self.didsave(self.view)

    @client_must_ready
    @must_valid_document
    def on_close(self):
        self.didclose(self.view)


class DocumentSynchronizeTextChangeListener(
    SynchronizeEventAdapter, sublime_plugin.TextChangeListener
):

    @client_must_ready
    def on_text_changed(self, changes: List[sublime.TextChange]):
        view = self.buffer.primary_view()
        if not is_valid_document(view):
            return
        self.didchange(view, [self._to_textchange(c) for c in changes])

    @staticmethod
    def _to_textchange(change: sublime.TextChange) -> TextChange:
        """"""
        start = (change.a.row, change.a.col)
        end = (change.b.row, change.b.col)
        return TextChange(start, end, change.str, change.len_utf8)
