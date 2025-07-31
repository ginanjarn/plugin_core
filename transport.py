"""transport handler"""

import re
from abc import ABC, abstractmethod
from io import BytesIO

from .child_process import ChildProcess


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


def wrap_rpc(content: bytes) -> bytes:
    """wrap content as rpc body"""
    header = b"Content-Length: %d\r\n" % len(content)
    separator = b"\r\n"
    return b"%s%s%s" % (header, separator, content)


def get_content_length(header: bytes) -> int:
    """get content length from header

    Return:
        content_length: int
    Raises:
        ValueError if content length not found
    """
    pattern = re.compile(rb"Content-Length: (\d+)")
    for line in header.splitlines():
        if match := pattern.match(line):
            return int(match.group(1))

    raise ValueError("unable get 'Content-Length'")


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
