"""client server api"""

import json
import logging
import os
import re
import threading
import subprocess
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Optional, Union, List, Dict, Callable, Any

from .errors import transform_error
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
    """loads json-rpc message"""

    dct = json.loads(json_str)
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

    json_str = json.dumps(dct)
    if as_bytes:
        return json_str.encode()
    return json_str


class HeaderError(ValueError):
    """header error"""


def wrap_rpc(content: bytes) -> bytes:
    """wrap content as rpc body"""
    header = b"Content-Length: %d\r\n" % len(content)
    separator = b"\r\n"
    return b"%s%s%s" % (header, separator, content)


def get_content_length(header: bytes) -> int:
    for line in header.splitlines():
        if match := re.match(rb"Content-Length: (\d+)", line):
            return int(match.group(1))

    raise HeaderError("unable get 'Content-Length'")


class Transport(ABC):
    """Transport abstraction"""

    @abstractmethod
    def connect(self) -> None:
        """open connection to server"""

    @abstractmethod
    def close(self) -> None:
        """close connection to server"""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write data to server"""

    @abstractmethod
    def read(self) -> bytes:
        """Read data from server"""


if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    # Hide created process window
    STARTUPINFO.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
else:
    STARTUPINFO = None


def recover_exception(
    default_factory: Callable[[Any], Any],
    *,
    exceptions: Optional[Union[Exception, tuple]] = None,
):
    """return default value if exception raised

    Arguments:
        default_factory: factory of default value
        excepttions: captured exceptions

    Returns:
        default_factory() result
    """

    # default
    exceptions = exceptions or Exception

    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions:
                return default_factory()

        return inner

    return wrapper


class ChildProcess:
    """Child Process"""

    def __init__(self, command: List[str], cwd: Optional[Path] = None):
        if not isinstance(command, list):
            raise ValueError("command value must list of str")

        self.command = command
        self.cwd = cwd

        self.process: subprocess.Popen = None
        self._run_event = threading.Event()

        # Prevent run process until termination done
        self._terminate_event = threading.Event()
        self._terminate_event.set()

    def is_running(self) -> bool:
        """If process is running"""
        if not self.process:
            return False
        return self.process.poll() is None

    def wait_process_running(self) -> None:
        """Wait process running"""
        self._run_event.wait()

    def run(self, env: Optional[dict] = None) -> None:
        """Run process"""

        # Wait if in termination process
        self._terminate_event.wait()

        # Prevent process reassignment
        if self.process and self.process.poll() is None:
            return

        print("execute '%s'" % shlex.join(self.command))

        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env or None,
            cwd=self.cwd or None,
            shell=True,
            bufsize=0,
            startupinfo=STARTUPINFO,
        )

        # Ready to call 'Popen()' object
        self._run_event.set()

        thread = threading.Thread(target=self._listen_stderr_task)
        thread.start()

    @property
    @recover_exception(BytesIO)
    def stdin(self):
        return self.process.stdin

    @property
    @recover_exception(BytesIO)
    def stdout(self):
        return self.process.stdout

    @property
    @recover_exception(BytesIO)
    def stderr(self):
        return self.process.stderr

    def _listen_stderr_task(self):
        prefix = f"[{self.command[0]}]"
        while bline := self.stderr.readline():
            print(prefix, bline.rstrip().decode())

        # Stderr return empty character, process is terminated
        self._terminate_event.set()

    def terminate(self) -> None:
        """Terminate process"""

        self._terminate_event.clear()
        self._run_event.clear()

        if not self.process:
            return

        self.process.kill()
        return_code = self.process.wait()
        print("process terminated with exit code", return_code)
        # Set to None to release 'Popen()' object from memory
        self.process = None


class StandardIO(Transport):
    """StandardIO Transport implementation"""

    def __init__(self, server: ChildProcess) -> None:
        self.server = server

    def connect(self) -> None:
        # connect with stdio
        pass

    def close(self) -> None:
        self.server.terminate()

    def write(self, data: bytes):
        self.server.wait_process_running()

        prepared_data = wrap_rpc(data)
        self.server.stdin.write(prepared_data)
        self.server.stdin.flush()

    def read(self):
        self.server.wait_process_running()

        # get header
        header_buffer = BytesIO()
        header_separator = b"\r\n"
        while line := self.server.stdout.readline():
            # header and content separated by newline with \r\n
            if line == header_separator:
                break
            header_buffer.write(line)

        header = header_buffer.getvalue()

        # no header received
        if not header:
            raise EOFError("stdout closed")

        try:
            content_length = get_content_length(header)
        except HeaderError as err:
            LOGGER.exception("header: %r", header_buffer.getvalue())
            raise err

        content_buffer = BytesIO()
        # Read until defined content_length received.
        missing = content_length
        while missing:
            if chunk := self.server.stdout.read(missing):
                n = content_buffer.write(chunk)
                missing -= n
            else:
                raise EOFError("stdout closed")

        return content_buffer.getvalue()


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
        def listen_message() -> Message:
            content = self.transport.read()
            try:
                message = loads(content)
            except json.JSONDecodeError as err:
                LOGGER.exception("content: %r", content)
                raise err

            return message

        while True:
            try:
                message = listen_message()

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
