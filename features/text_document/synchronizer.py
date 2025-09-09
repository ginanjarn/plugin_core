from functools import wraps
from typing import List
import sublime
import sublime_plugin

from ...document import Document, TextChange, is_valid_document
from ...uri import path_to_uri


class DocumentSynchronizerMixins:
    client = None

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


def client_must_ready(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.client and self.client.is_ready():
            return func(self, *args, **kwargs)
        return None

    return wrapper


class DocumentSynchronizeEventListener(
    DocumentSynchronizerMixins, sublime_plugin.EventListener
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
    DocumentSynchronizerMixins, sublime_plugin.TextChangeListener
):

    @client_must_ready
    def on_text_changed(self, changes: List[sublime.TextChange]):
        view = self.buffer.primary_view()
        if not is_valid_document(view):
            return
        self.didchange(view, [self._to_text_change(c) for c in changes])

    @staticmethod
    def _to_text_change(change: sublime.TextChange) -> TextChange:
        """"""
        start = (change.a.row, change.a.col)
        end = (change.b.row, change.b.col)
        return TextChange(start, end, change.str, change.len_utf8)


def must_initialized(func):
    """exec if initialized"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.session.is_initialized():
            return None
        return func(self, *args, **kwargs)

    return wrapper


class DocumentSynchronizerMixins:

    @must_initialized
    def textdocument_didopen(self, view: sublime.View, *, reload: bool = False):
        # check if view not closed
        if not (view and view.is_valid()):
            return

        self.session.diagnostic_manager.set_active_view(view)

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
            self.message_pool.send_notification(
                "textDocument/didOpen",
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

    @must_initialized
    def textdocument_didsave(self, view: sublime.View):
        if document := self.session.get_document(view):
            self.message_pool.send_notification(
                "textDocument/didSave",
                {"textDocument": {"uri": path_to_uri(document.file_name)}},
            )

        else:
            # untitled document not yet loaded to server
            self.textdocument_didopen(view)

    @must_initialized
    def textdocument_didclose(self, view: sublime.View):

        # Check if the document open in multiple view like side-by-side layout
        documents = self.session.get_documents(
            filter_func=lambda doc: doc.file_name == view.file_name()
        )
        if len(documents) > 1:
            # Remove the document but don't notify to server
            self.session.remove_document(view)
            return

        if document := self.session.get_document(view):
            self.message_pool.send_notification(
                "textDocument/didClose",
                {"textDocument": {"uri": path_to_uri(document.file_name)}},
            )

        self.session.diagnostic_manager.remove(view)
        self.session.remove_document(view)

    @must_initialized
    def textdocument_didchange(self, view: sublime.View, changes: List[TextChange]):
        if document := self.session.get_document(view):
            self.message_pool.send_notification(
                "textDocument/didChange",
                {
                    "contentChanges": [textchange_to_rpc(c) for c in changes],
                    "textDocument": {
                        "uri": path_to_uri(document.file_name),
                        "version": document.version,
                    },
                },
            )


def textchange_to_rpc(text_change: TextChange) -> dict:
    """"""
    start = text_change.start
    end = text_change.end
    return {
        "range": {
            "start": {"line": start[0], "character": start[1]},
            "end": {"line": end[0], "character": end[1]},
        },
        "rangeLength": text_change.length,
        "text": text_change.text,
    }
