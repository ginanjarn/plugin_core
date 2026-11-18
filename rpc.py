"""JSONRPC implementation"""

import logging
import threading
from functools import wraps
from typing import Any, Dict, Optional

import sublime

from .errors import transform_error
from .message import (
    Method,
    Params,
    Result,
    dumps_rpc2,
    loads_rpc2,
    new_notification,
    new_request,
    new_response,
)
from .session import Session
from .transport import Transport

LOGGER = logging.getLogger(__name__)


class Context(dict):
    """Context data passed to handlers (e.g., session state, metadata)."""


class MessageExchangeBase:
    """Base class for message exchange over a transport."""

    def __init__(self, transport: Transport):
        self.transport: Transport = transport

    def send(self, message: dict) -> None:
        """Send a message over the transport."""
        try:
            content = dumps_rpc2(message, as_bytes=True)
            self.transport.write(content)
        except Exception as err:
            LOGGER.error("Failed to send message: %s", err)

    def recv(self) -> dict:
        """Receive a message from the transport."""
        try:
            content = self.transport.read()
            return loads_rpc2(content)
        except Exception as err:
            LOGGER.error("Failed to receive/parse message: %s", err)
            raise


class RequestManager:
    """RequestManager manage method mapped to request_id."""

    def __init__(self):
        self.pending: Dict[int, Method] = {}
        self.request_count = 0

        self._lock = threading.RLock()

    def _with_lock(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            with self._lock:
                return func(self, *args, **kwargs)

        return wrapper

    @_with_lock
    def reset(self) -> None:
        self.pending.clear()
        self.request_count = 0

    @_with_lock
    def add(self, method: Method) -> int:
        """add pending request

        Return:
            request_count: int
        """
        self.request_count += 1
        self.pending[self.request_count] = method

        return self.request_count

    @_with_lock
    def pop(self, request_id: int) -> Optional[Method]:
        """pop pending request

        Return:
            method: Method
        """
        return self.pending.pop(request_id, None)

    @_with_lock
    def pop_pending(self, method: Method) -> Optional[int]:
        """pop pending request"""
        matches = (req_id for req_id, meth in self.pending.items() if meth == method)
        if req_id := next(matches, None):
            del self.pending[req_id]
            return req_id
        return None

    @_with_lock
    def cancel_all(self):
        """cancel all pending request"""
        self.pending.clear()


class ClientCommandMixin(MessageExchangeBase):
    """Client command interface"""

    def __init__(self):
        self.request_manager = RequestManager()

    def request(self, method: Method, params: Params) -> None:
        # cancel pending request
        if pending_id := self.request_manager.pop_pending(method):
            self.notify("$/cancelRequest", {"id": pending_id})

        req_id = self.request_manager.add(method)
        self.send(new_request(req_id, method, params))

    def _handle_response(self, context: Context, message: dict) -> None:
        method = self.request_manager.pop(message.get("id"))
        if method is None:
            return

        if error := message.get("error"):
            LOGGER.error("Response error(%d): %s", message["id"], error["message"])
            return

        try:
            self._handle(context, method, message.get("result"))
        except Exception as err:
            LOGGER.exception(err, exc_info=True)

    def notify(self, method: Method, params: Params) -> None:
        if method in {
            "textDocument/didOpen",
            "textDocument/didChange",
        }:
            # cancel all current request
            self.request_manager.cancel_all()
        self.send(new_notification(method, params))


class ServerCommandMixin(MessageExchangeBase):
    """Server command interface"""

    def _handle_request(self, context: Context, message: dict) -> None:
        try:
            result = self._handle(context, message["method"], message.get("params"))
            self._respond(message["id"], result, None)
        except Exception as err:
            LOGGER.exception("Error handling request", exc_info=True)
            error = transform_error(err)
            self._respond(message["id"], None, error)

    def _respond(
        self, id: int, result: Optional[Any] = None, error: Optional[dict] = None
    ) -> None:
        self.send(new_response(id, result, error))

    def _handle_notification(self, context: Context, message: dict) -> None:
        try:
            self._handle(context, message["method"], message["params"])
        except Exception as err:
            LOGGER.exception("Error handling notification %s", err, exc_info=True)


class RPC(ClientCommandMixin, ServerCommandMixin, MessageExchangeBase):
    """RPC object"""

    def __init__(self, transport: Transport):
        MessageExchangeBase.__init__(self, transport)
        super().__init__()

        self.session = Session()
        self._stop_event = threading.Event()
        self._listen_thread: Optional[threading.Thread] = None

    def is_ready(self) -> bool:
        """check client is ready"""
        return self.transport.is_connected() and self.session.is_initialized()

    def connect(self) -> None:
        if self.transport.is_connected():
            return

        sublime.status_message("connecting to language server...")
        self.transport.connect()

        # sometimes the server stop working
        # we must reset the state before run server
        self.session.reset()
        self.listen()

    def disconnect(self) -> None:
        self._stop_event.set()
        self.transport.disconnect()

    def listen(self) -> None:
        self.request_manager.reset()

        self._stop_event.clear()
        self._listen_thread = threading.Thread(target=self._listen_task, daemon=True)
        self._listen_thread.start()

    def _listen_task(self) -> None:
        while not self._stop_event.is_set():
            try:
                message = self.recv()
            except ConnectionError:
                break
            except Exception as err:
                LOGGER.error("Error parsing message: %s", err)
                break

            try:
                # context required in 'LSClient' params
                context = Context()
                has_id = "id" in message

                if "method" in message:
                    # server command
                    if has_id:
                        self._handle_request(context, message)
                    else:
                        self._handle_notification(context, message)
                else:
                    # server response
                    self._handle_response(context, message)

            except Exception:
                LOGGER.error("Error _handle message: %r", message, exc_info=True)
                break

        # disconnect
        self.disconnect()
