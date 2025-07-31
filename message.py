"""message handler"""

import logging
import threading
from dataclasses import dataclass, asdict
from json import (
    loads as json_loads,
    dumps as json_dumps,
)
from typing import Optional, Union, Dict, Callable, Any

from .errors import transform_error
from .transport import Transport
from ..constant import LOGGING_CHANNEL

LOGGER = logging.getLogger(LOGGING_CHANNEL)


class MethodName(str):
    """Method name"""


@dataclass
class Message:
    """JSON-RPC Message interface"""


@dataclass
class Notification(Message):
    method: MethodName
    params: Optional[Union[dict, list]] = None


@dataclass
class Request(Message):
    id: int
    method: MethodName
    params: Optional[Union[dict, list]] = None


@dataclass
class Response(Message):
    id: int
    result: Optional[Union[dict, list]] = None
    error: Optional[dict] = None


def loads(json_str: Union[str, bytes]) -> Message:
    """loads json-rpc message

    Raises:
      * json.JsonDecodeError if fail loads json
      * ValueError if invalid jsonrpc version
    """

    dct = json_loads(json_str)
    try:
        if (jsonrpc_version := dct.pop("jsonrpc")) and jsonrpc_version != "2.0":
            raise ValueError("invalid jsonrpc version")
    except KeyError as err:
        raise ValueError("JSON-RPC 2.0 is required") from err

    if dct.get("method"):
        id = dct.get("id")
        if id is None:
            return Notification(**dct)
        return Request(**dct)
    return Response(**dct)


def dumps(message: Message, as_bytes: bool = False) -> Union[str, bytes]:
    """dumps json-rpc message"""

    dct = asdict(message)
    dct["jsonrpc"] = "2.0"

    if isinstance(message, Response):
        if not message.error:
            del dct["error"]
        else:
            del dct["result"]

    json_str = json_dumps(dct)
    if as_bytes:
        return json_str.encode()
    return json_str


class RequestCanceled(Exception):
    """Request Canceled"""


class RequestManager:
    """RequestManager manage method mapped to request_id."""

    def __init__(self):
        self.methods_map: Dict[int, MethodName] = {}
        self.request_count = 0

        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self.methods_map.clear()
            self.request_count = 0

    def add(self, method: MethodName) -> int:
        """add request method to request_map

        Return:
            request_count: int
        """
        with self._lock:
            self.request_count += 1
            self.methods_map[self.request_count] = method

            return self.request_count

    def pop(self, request_id: int) -> MethodName:
        """pop method paired with request_id

        Return:
            method: str
        Raises:
            RequestCanceled if request_id not found
        """

        with self._lock:
            try:
                return self.methods_map.pop(request_id)
            except KeyError as err:
                raise RequestCanceled(request_id) from err

    def cancel(self, method: MethodName) -> Optional[int]:
        """cancel older request

        Returns:
            canceled request id or None
        """

        with self._lock:
            canceled_id = None

            for req_id, meth in self.methods_map.items():
                if meth == method:
                    canceled_id = req_id
                    break
            else:
                # no match found
                return None

            # delete after for loop to prevent RuntimeError("dictionary changed size during iteration")
            del self.methods_map[canceled_id]
            return canceled_id

    def cancel_all(self):
        """cancel all request"""

        with self._lock:
            self.methods_map.clear()


MessageHandler = Callable[[MethodName, Union[dict, list]], Any]


class MessagePool:
    """Client - Server Message Pool"""

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
        content = dumps(message, as_bytes=True)
        self.transport.write(content)

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

    def listen(self) -> None:
        self._reset_managers()

        thread = threading.Thread(target=self._listen_task, daemon=True)
        thread.start()

    def handle_message(self, message: Message) -> None:
        handler_map = {
            Notification: self._handle_notification,
            Request: self._handle_request,
            Response: self._handle_response,
        }
        return handler_map[type(message)](message)

    def _handle_request(self, message: Request) -> None:
        result = None
        error = None
        try:
            result = self.handle_func(message.method, message.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)
            error = transform_error(err)

        self.send_response(message.id, result, error)

    def _handle_notification(self, message: Notification) -> None:
        try:
            self.handle_func(message.method, message.params)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)

    def _handle_response(self, message: Response) -> None:
        try:
            method = self._request_manager.pop(message.id)
        except (RequestCanceled, KeyError):
            # ignore canceled response
            return

        try:
            self.handle_func(method, message)
        except Exception as err:
            LOGGER.exception(err, exc_info=True)

    def send_request(self, method: MethodName, params: dict) -> None:
        # cancel previous request with same method
        if prev_request := self._request_manager.cancel(method):
            self.send_notification("$/cancelRequest", {"id": prev_request})

        req_id = self._request_manager.add(method)
        self.send_message(Request(req_id, method, params))

    def send_notification(self, method: MethodName, params: dict) -> None:
        if method in {
            "textDocument/didOpen",
            "textDocument/didChange",
        }:
            # cancel all current request
            self._request_manager.cancel_all()
        self.send_message(Notification(method, params))

    def send_response(
        self, id: int, result: Optional[dict] = None, error: Optional[dict] = None
    ) -> None:
        self.send_message(Response(id, result, error))
