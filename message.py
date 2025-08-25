"""message handler"""

import logging
import threading
from dataclasses import dataclass, asdict
from json import (
    loads as json_loads,
    dumps as json_dumps,
    JSONDecodeError,
)
from typing import Optional, Union, Dict, Callable, Any

from .errors import ParseError, transform_error
from .transport import Transport
from ..constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


Method = str
Params = Optional[Union[dict, list]]


@dataclass
class Message:
    """JSON-RPC Message interface"""


@dataclass
class Notification(Message):
    method: Method
    params: Params = None


@dataclass
class Request(Message):
    id: int
    method: Method
    params: Params = None


@dataclass
class Response(Message):
    id: int
    result: Optional[Union[dict, list]] = None
    error: Optional[dict] = None


JSONRPC_KEY = "jsonrpc"
JSONRPC_VERSION = "2.0"


def loads(json_str: Union[str, bytes]) -> Message:
    """loads json-rpc message

    Raises:
      * json.JsonDecodeError if fail loads json
      * ValueError if invalid jsonrpc version
    """

    try:
        dct = json_loads(json_str)
    except JSONDecodeError as err:
        raise ParseError from err

    version = dct.pop(JSONRPC_KEY, "1.0")
    if version != JSONRPC_VERSION:
        raise ValueError("invalid json-rpc version")

    # Request and Notification contain 'method' key
    if "method" in dct:
        if "id" in dct:
            return Request(**dct)
        return Notification(**dct)
    return Response(**dct)


def dumps(message: Message, as_bytes: bool = False) -> Union[str, bytes]:
    """dumps json-rpc message"""

    dct = asdict(message)
    dct[JSONRPC_KEY] = JSONRPC_VERSION

    if isinstance(message, Response):
        # Response only contain one of 'result' or 'error' field
        if not message.error:
            del dct["error"]
        else:
            del dct["result"]

    json_str = json_dumps(dct)
    if as_bytes:
        return json_str.encode()
    return json_str


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

    def cancel(self, method: Method) -> Optional[int]:
        """cancel older request

        Returns:
            canceled request id or None
        """

        with self._lock:
            if found := [id for id, meth in self.methods_map.items() if meth == method]:
                canceled_id = found[0]
                del self.methods_map[canceled_id]
                return canceled_id

            return None

    def cancel_all(self):
        """cancel all request"""

        with self._lock:
            self.methods_map.clear()


MessageHandler = Callable[[Method, Union[Params, Response]], Any]


class MessageManager:

    def __init__(
        self,
        transport: Transport,
        handle_func: MessageHandler,
    ):
        self.transport = transport
        self.handle_func = handle_func
        self._request_manager = RequestManager()

    def _reset_managers(self) -> None:
        self._request_manager.reset()

    def send_message(self, message: Message) -> None:
        """send message"""
        content = dumps(message, as_bytes=True)
        self.transport.write(content)

    def listen(self) -> None:
        """listen message"""
        self._reset_managers()

        thread = threading.Thread(target=self._listen_task, daemon=True)
        thread.start()

    def _listen_task(self) -> None:
        """listen message task"""
        raise NotImplementedError


class CommandInterfaceMixins(MessageManager):
    """Command interface to control server"""

    def send_request(self, method: Method, params: Params) -> None:
        # cancel previous request with same method
        if prev_request := self._request_manager.cancel(method):
            self.send_notification("$/cancelRequest", {"id": prev_request})

        req_id = self._request_manager.add(method)
        self.send_message(Request(req_id, method, params))

    def _handle_response(self, message: Response) -> None:
        try:
            method = self._request_manager.pop(message.id)
        except KeyError:
            # ignore canceled response
            return

        try:
            self.handle_func(method, message)
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


class ReceivedMessageHandlerMixins(MessageManager):
    """Handle message received from server"""

    def _handle_request(self, message: Request) -> None:
        result = None
        error = None
        try:
            result = self.handle_func(message.method, message.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)
            error = transform_error(err)

        self._send_response(message.id, result, error)

    def _send_response(
        self, id: int, result: Optional[Any] = None, error: Optional[dict] = None
    ) -> None:
        self.send_message(Response(id, result, error))

    def _handle_notification(self, message: Notification) -> None:
        try:
            self.handle_func(message.method, message.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)


class MessagePool(CommandInterfaceMixins, ReceivedMessageHandlerMixins):
    """Client - Server Message Pool"""

    def handle_message(self, message: Message) -> None:
        handler_map = {
            Notification: self._handle_notification,
            Request: self._handle_request,
            Response: self._handle_response,
        }
        return handler_map[type(message)](message)

    def _listen_task(self) -> None:

        while True:
            try:
                content = self.transport.read()
                message = loads(content)

            except EOFError:
                # stdout closed
                break

            except Exception as err:
                LOGGER.exception(err, exc_info=True)
                self.transport.close()
                break

            try:
                self.handle_message(message)
            except Exception:
                LOGGER.exception("error handle message: %r", message, exc_info=True)
