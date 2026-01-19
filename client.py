"""client object"""

import logging
import threading
import sys
from collections.abc import MutableMapping
from functools import lru_cache, wraps
from typing import (
    Optional,
    Dict,
    Callable,
    Any,
    Union,
    Iterator,
)
import sublime

from .child_process import ChildProcess
from .diagnostics import ReportSettings
from .errors import MethodNotFound, transform_error
from .message import (
    Message,
    Request,
    Notification,
    Method,
    Params,
    Response,
    Result,
    loads,
    dumps,
)
from .session import Session
from .transport import Transport
from ..constant import LOGGING_CHANNEL

_KT = type
_VT = type


LOGGER = logging.getLogger(LOGGING_CHANNEL)


class Context(MutableMapping):
    """Context data object

    A dict-like object with thread locking.
    """

    def __init__(self, *args, **kwargs) -> None:
        self.data = dict(*args, **kwargs)
        self._lock = threading.Lock()

    def lock(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            with self._lock:
                return func(*args, **kwargs)

        return wrapper

    @lock
    def __setitem__(self, key: _KT, value: _VT) -> None:
        self.data[key] = value

    @lock
    def __getitem__(self, key: _KT) -> _VT:
        return self.data[key]

    @lock
    def __delitem__(self, key: _KT) -> None:
        del self.data[key]

    @lock
    def __iter__(self) -> Iterator[_KT]:
        yield from iter(self.data)


RequestHandler = Callable[[Context, Params], Any]
NotificationHandler = Callable[[Context, Params], None]
ResponseHandler = Callable[[Context, Response], None]
SessionMessageHandler = Union[RequestHandler, NotificationHandler, ResponseHandler]


@lru_cache
def normalize_method(method: Method) -> Method:
    """normalize_method

    Nomalization steps:
    * replace '/' with '_'
    * convert to lower case

    e.g.: textDocument/completion -> textdocument_completion
    """
    return method.replace("/", "_").lower()


class ServerProcessManagerMixin:

    _start_server_lock = threading.Lock()

    def __init__(self, *args, **kwargs) -> None:
        self.server_process: ChildProcess

    def start_server(self, env: Optional[dict] = None) -> None:
        """"""
        # only one thread can run server
        if self._start_server_lock.locked():
            return

        with self._start_server_lock:
            if not self.server_process.is_running():
                sublime.status_message("running language server...")
                # sometimes the server stop working
                # we must reset the state before run server
                self.reset_session()

                self.server_process.run(env)
                self.listen()

    def terminate(self) -> None:
        """terminate session"""
        self.server_process.terminate()
        self.reset_session()


class MessageHandlerMixins:

    def __init__(self):
        self.handler_map: Dict[str, SessionMessageHandler]

    def handle_command(
        self,
        context: Context,
        method: Method,
        param_or_result: Union[Params, Result],
    ) -> Optional[Any]:
        """"""
        try:
            func = self.handler_map[normalize_method(method)]
        except KeyError:
            raise MethodNotFound

        return func(context, param_or_result)

    def register_handler(self, method: Method, function: SessionMessageHandler) -> None:
        """"""
        self.handler_map[normalize_method(method)] = function


class RequestManager:
    """RequestManager manage method mapped to request_id."""

    def __init__(self):
        self.methods_map: Dict[int, Method] = {}
        self.request_count = 0

        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self.methods_map.clear()
            self.request_count = 0

    def add(self, method: Method) -> int:
        """add request method to request_map

        Return:
            request_count: int
        """
        with self._lock:
            self.request_count += 1
            self.methods_map[self.request_count] = method

            return self.request_count

    def pop(self, request_id: int) -> Method:
        """pop method paired with request_id

        Return:
            method: str
        Raises:
            KeyError if request_id not found
        """

        with self._lock:
            return self.methods_map.pop(request_id)

    def is_pending_request(self, method: Method) -> bool:
        """check if same method has pending request"""

        with self._lock:
            return method in self.methods_map

    def cancel_all(self):
        """cancel all request"""

        with self._lock:
            self.methods_map.clear()


class _MessageExchangeBase(MessageHandlerMixins):

    def __init__(self, *args, **kwargs):
        self.transport: Transport
        self._request_manager: RequestManager

    def _reset_managers(self) -> None:
        self._request_manager.reset()

    def send_message(self, message: Message) -> None:
        """send message"""
        content = dumps(message, as_bytes=True)
        self.transport.write(content)

    def recv_message(self) -> Message:
        content = self.transport.read()
        return loads(content)

    def listen(self) -> None:
        """listen message"""
        self._reset_managers()

        thread = threading.Thread(target=self._listen_task, daemon=True)
        thread.start()


class ClientCommand(_MessageExchangeBase):
    """Client command interface"""

    def send_request(self, method: Method, params: Params) -> None:
        # cancel pending request
        if self._request_manager.is_pending_request(method):
            pending_id = self._request_manager.pop(method)
            self.send_notification("$/cancelRequest", {"id": pending_id})

        req_id = self._request_manager.add(method)
        self.send_message(Request(req_id, method, params))

    def _handle_response(self, context: Context, response: Response) -> None:
        try:
            method = self._request_manager.pop(response.id)
        except KeyError:
            # ignore canceled response
            return

        if error := response.error:
            print(error["message"], file=sys.stderr)
            return

        try:
            self.handle_command(context, method, response.result)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)

    def send_notification(self, method: Method, params: Params) -> None:
        if method in {
            "textDocument/didOpen",
            "textDocument/didChange",
        }:
            # cancel all current request
            self._request_manager.cancel_all()
        self.send_message(Notification(method, params))


class ServerCommand(_MessageExchangeBase):
    """Server command interface"""

    def _handle_request(self, context: Context, request: Request) -> None:
        result = None
        error = None
        try:
            result = self.handle_command(context, request.method, request.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)
            error = transform_error(err)

        self._send_response(request.id, result, error)

    def _send_response(
        self, id: int, result: Optional[Any] = None, error: Optional[dict] = None
    ) -> None:
        self.send_message(Response(id, result, error))

    def _handle_notification(
        self, context: Context, notification: Notification
    ) -> None:
        try:
            self.handle_command(context, notification.method, notification.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)


class ListenTaskImpl(_MessageExchangeBase):

    def _listen_task(self) -> None:
        handler_map = {
            Notification: self._handle_notification,
            Request: self._handle_request,
            Response: self._handle_response,
        }

        while True:
            try:
                message = self.recv_message()
                typ = type(message)
                handler_map[typ](self.session, message)

            except EOFError:
                # stdout closed
                break
            except Exception:
                LOGGER.error("error handle message: %r", message, exc_info=True)
                break

        # terminated
        self.terminate()


class MessageExchangeMixin(ListenTaskImpl, ClientCommand, ServerCommand):
    """Client - Server Message Manager"""


class BaseClient(MessageExchangeMixin, ServerProcessManagerMixin):
    """"""

    def __init__(
        self,
        process: ChildProcess,
        transport: Transport,
        report_settings: ReportSettings = None,
    ):

        self.server_process = process
        self.transport = transport

        # server message handler
        self.handler_map: Dict[Method, SessionMessageHandler] = dict()
        self._set_default_handler()

        self._request_manager = RequestManager()
        # session data
        self.session = Session(report_settings=report_settings)

    def _set_default_handler(self):
        """set default handler

        Register class method which has following rule as method handler :
        * method name start with 'handle_'
        * replace '/' with '_'
        * convert to lower case

        example:
          ---------------------------------------------------------
          rpc method                 handler method name
          ---------------------------------------------------------
          textDocument/completion    handle_textdocument_completion
          textDocument/hover         handle_textdocument_hover
          textDocument/codeAction    handle_textdocument_codeaction
          ---------------------------------------------------------

        """

        for name in dir(self):
            attribute = getattr(self, name)
            if not callable(attribute):
                continue

            prefix = "handle_"
            if name.startswith(prefix):
                method = name[len(prefix) :]
                self.handler_map[normalize_method(method)] = attribute

    def reset_session(self) -> None:
        """reset session state"""
        self.session.reset()

    def is_ready(self) -> bool:
        """check session is ready"""
        return self.server_process.is_running() and self.session.is_initialized()
