"""transport handler"""

from abc import ABC, abstractmethod
from io import BytesIO
from threading import Event

from .child_process import ChildProcess


class Transport(ABC):
    """Transport abstraction"""

    @abstractmethod
    def connect(self) -> None:
        """connection to server"""

    @abstractmethod
    def disconnect(self) -> None:
        """disconnect from server"""

    @abstractmethod
    def is_connected(self) -> bool:
        """check is connected to server"""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write data to server"""

    @abstractmethod
    def read(self) -> bytes:
        """Read data from server

        Return:
            content: bytes

        Raises:
            EOFError: if stdout closed
            ValueError
        """


HEADER_SEPARATOR = b"\r\n"


def set_header(content: bytes) -> bytes:
    """set rpc header"""
    header = b"Content-Length: %d\r\n" % len(content)
    return b"%s%s%s" % (header, HEADER_SEPARATOR, content)


def get_content_length(header: bytes) -> int:
    """get content length from header

    Return:
        content_length: int
    Raises:
        ValueError if content length not found
    """
    field_text = b"Content-Length: "
    field_end = 16  # => len(field_text)

    for line in header.splitlines(keepends=False):
        if line[:field_end] == field_text:
            return int(line[field_end:])

    raise ValueError("unable get 'Content-Length'")


class StandardIO(Transport):
    """StandardIO Transport implementation"""

    def __init__(self, server: ChildProcess) -> None:
        self.server = server
        self._is_connected = False
        self._connect_event = Event()

    def connect(self) -> None:
        self._is_connected = True
        self._connect_event.set()

    def disconnect(self) -> None:
        self.server.terminate()
        self._connect_event.clear()
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def write(self, data: bytes):
        if not self._is_connected:
            self._connect_event.wait()

        prepared_data = set_header(data)
        self.server.stdin.write(prepared_data)
        self.server.stdin.flush()

    def read(self):
        if not self._is_connected:
            self._connect_event.wait()

        # get header
        header_buffer = BytesIO()
        # loop until meet header separator
        while line := self.server.stdout.readline():
            if line == HEADER_SEPARATOR:
                break
            header_buffer.write(line)

        if header := header_buffer.getvalue():
            content_length = get_content_length(header)
        else:
            raise EOFError("stdout closed")

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
