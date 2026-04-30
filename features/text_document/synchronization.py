from typing import List
import sublime
import sublime_plugin

from ...client_internal import BaseClient
from ...document import Document, is_valid_document, TextChange
from ...uri import path_to_uri
from ...utils import client_must_ready, on_new_thread
from ...lsprotocol.lsprotocol import TextDocumentContentChangePartial


class DocumentSynchronizerMixins(BaseClient):

    @on_new_thread
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

    @on_new_thread
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

    @on_new_thread
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

    @on_new_thread
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


class SynchronizeEventAdapter:
    client: DocumentSynchronizerMixins = None

    def didopen(self, view: sublime.View, *, reload: bool = False):
        if not is_valid_document(view):
            return
        self.client.textdocument_didopen(view, reload=reload)

    def didsave(self, view: sublime.View):
        if not is_valid_document(view):
            return
        self.client.textdocument_didsave(view)

    def didclose(self, view: sublime.View):
        if not is_valid_document(view):
            return
        self.client.textdocument_didclose(view)

    def didchange(self, view: sublime.View, changes: List[TextChange]):
        if not is_valid_document(view):
            return
        self.client.textdocument_didchange(view, changes)


class DocumentSynchronizeEventListener(
    SynchronizeEventAdapter, sublime_plugin.EventListener
):

    @client_must_ready
    def on_activated_async(self, view: sublime.View):
        self.didopen(view)

    @client_must_ready
    def on_load_async(self, view: sublime.View):
        self.didopen(view, reload=True)

    @client_must_ready
    def on_reload_async(self, view: sublime.View):
        self.didopen(view, reload=True)

    @client_must_ready
    def on_revert_async(self, view: sublime.View):
        self.didopen(view, reload=True)

    @client_must_ready
    def on_post_save_async(self, view: sublime.View):
        self.didsave(view)

    @client_must_ready
    def on_close(self, view: sublime.View):
        self.didclose(view)

    @client_must_ready
    def on_associate_buffer_async(self, buffer: sublime.Buffer):
        # close all associated buffer
        for view in buffer.views():
            self.didclose(view)
        # then reopen active view
        self.didopen(buffer.primary_view())


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
