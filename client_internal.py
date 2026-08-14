"""client object"""

from __future__ import annotations

import logging
import threading
from functools import wraps
from typing import Optional, Dict, Any

import sublime

from .child_process import ChildProcess
from .errors import transform_error
from .message import (
    new_request,
    new_notification,
    Method,
    Params,
    new_response,
    Result,
    loads_rpc2,
    dumps_rpc2,
)
from .safe_dict import SafeDict
from .session import Session
from .lsprotocol.client import Client as LSClient
from .transport import Transport
from ..constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class Context(SafeDict):
    """Context data"""


class _MessageExchangeBase:

    def __init__(self, transport: Transport):
        self.transport = transport

    def send(self, message: dict) -> None:
        """send message"""
        content = dumps_rpc2(message, as_bytes=True)
        self.transport.write(content)

    def recv(self) -> dict:
        """receive message"""
        content = self.transport.read()
        return loads_rpc2(content)

    def _handle(
        self, context: Context, method: Method, param_or_result: Optional[Any] = None
    ) -> Optional[Result]:
        """handle command"""
        raise NotImplementedError("_handle")

    def listen(self) -> None:
        """listen message"""
        raise NotImplementedError("listen")


class RequestManager:
    """RequestManager manage method mapped to request_id."""

    def __init__(self):
        self.pending: Dict[int, Method] = {}
        self.request_count = 0

        self._lock = threading.Lock()

    def lock(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            with self._lock:
                return func(self, *args, **kwargs)

        return wrapper

    @lock
    def reset(self) -> None:
        self.pending.clear()
        self.request_count = 0

    @lock
    def add(self, method: Method) -> int:
        """add pending request

        Return:
            request_count: int
        """
        self.request_count += 1
        self.pending[self.request_count] = method

        return self.request_count

    @lock
    def pop(self, request_id: int) -> Optional[Method]:
        """pop pending request

        Return:
            method: Method
        """
        return self.pending.pop(request_id, None)

    @lock
    def pop_pending(self, method: Method) -> Optional[int]:
        """pop pending request"""
        matches = (id for id, meth in self.pending.items() if meth == method)
        if id := next(matches, None):
            del self.pending[id]
            return id
        return None

    @lock
    def cancel_all(self):
        """cancel all pending request"""
        self.pending.clear()


class ClientCommand(_MessageExchangeBase):
    """Client command interface"""

    def __init__(self, transport: Transport):
        super().__init__(transport)
        self.request_manager = RequestManager()

    def request(self, method: Method, params: Params) -> None:
        # cancel pending request
        if pending_id := self.request_manager.pop_pending(method):
            self.notify("$/cancelRequest", {"id": pending_id})

        req_id = self.request_manager.add(method)
        self.send(new_request(req_id, method, params))

    def _handle_response(self, context: Context, message: dict) -> None:
        method = self.request_manager.pop(message["id"])
        if method is None:
            return

        if error := message.get("error"):
            print(error["message"])
            return

        try:
            self._handle(context, method, message["result"])
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


class ServerCommand(_MessageExchangeBase):
    """Server command interface"""

    def _handle_request(self, context: Context, message: dict) -> None:
        result = None
        error = None
        try:
            result = self._handle(context, message["method"], message["params"])
        except Exception as err:
            LOGGER.exception(err, exc_info=True)
            error = transform_error(err)

        self._respond(message.id, result, error)

    def _respond(
        self, id: int, result: Optional[Any] = None, error: Optional[dict] = None
    ) -> None:
        self.send(new_response(id, result, error))

    def _handle_notification(self, context: Context, message: dict) -> None:
        try:
            self._handle(context, message["method"], message["params"])
        except Exception as err:
            LOGGER.exception(err, exc_info=True)


class RPC(ClientCommand, ServerCommand, LSClient):
    """Remote Procedure Call"""

    def __init__(self, transport: Transport):
        super().__init__(transport)
        self.session = Session()

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
        self.transport.disconnect()

    def listen(self) -> None:
        self.request_manager.reset()

        thread = threading.Thread(target=self._listen_task, daemon=True)
        thread.start()

    def _listen_task(self) -> None:
        while True:
            try:
                message = self.recv()
            except ConnectionError:
                break
            except Exception as err:
                LOGGER.error("error parsing message: %s", err)
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
                LOGGER.error("error handle message: %r", message, exc_info=True)
                break

        # disconnent
        self.disconnect()

    def _handle(
        self, context: Context, method: Method, param_or_result: Optional[Any] = None
    ) -> Optional[Result]:
        # adapter for 'LSClient.handle'
        return self.handle(context, method, param_or_result)


class BaseClient(RPC):
    """"""

    def __init__(
        self,
        process: ChildProcess,
        transport: Transport,
    ):
        super().__init__(transport)
        self.server_process = process
