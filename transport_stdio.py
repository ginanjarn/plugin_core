"""StandardIO Transport implementation for Language Server Protocol."""

import logging
from io import BytesIO
from threading import Event

from .child_process import ChildProcess
from .transport import Transport

HEADER_SEPARATOR = b"\r\n"
LOGGER = logging.getLogger(__name__)


def set_header(content: bytes) -> bytes:
    """Attach Content-Length header to RPC message."""
    header = f"Content-Length: {len(content)}\r\n".encode("ascii")
    return header + HEADER_SEPARATOR + content


def get_content_length(header: bytes) -> int:
    """Extract content length from header.

    Raises:
        ValueError: if Content-Length is missing or invalid.
    """
    field_text = b"Content-Length: "
    field_end = len(field_text)

    for line in header.splitlines(keepends=False):
        if line.startswith(field_text):
            try:
                return int(line[field_end:])
            except ValueError as err:
                raise ValueError(
                    f"Invalid Content-Length value in header: {line!r}"
                ) from err

    raise ValueError(f"Content-Length not found in header: {header!r}")


class StandardIO(Transport):
    """Transport implementation using child process stdin/stdout pipes."""

    def __init__(self, server: ChildProcess) -> None:
        self.server = server
        self._is_connected = False
        self._connect_event = Event()

    def connect(self) -> None:
        """Mark transport as connected if server is running."""
        if not self.server.is_running():
            raise ConnectionError("Server is not running")
        self._is_connected = True
        self._connect_event.set()

    def disconnect(self) -> None:
        """Terminate server and mark transport as disconnected."""
        try:
            self.server.terminate()
        except Exception as err:
            LOGGER.warning("Error terminating server: %s", err)
        finally:
            self._connect_event.clear()
            self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def write(self, data: bytes) -> None:
        """Write framed data to server stdin."""
        if not self._is_connected:
            if not self._connect_event.wait(timeout=5):
                raise ConnectionError("Timeout waiting for connection")

        prepared_data = set_header(data)
        try:
            self.server.stdin.write(prepared_data)
            self.server.stdin.flush()
        except Exception as err:
            self._is_connected = False
            raise ConnectionError("Disconnected from server") from err

    def read(self) -> bytes:
        """Read framed data from server stdout."""
        if not self._is_connected:
            if not self._connect_event.wait(timeout=5):
                raise ConnectionError("Timeout waiting for connection")

        # Read header
        header_buffer = BytesIO()
        while True:
            line = self.server.stdout.readline()
            if not line:
                self._is_connected = False
                raise ConnectionError("Server closed connection")
            if line == HEADER_SEPARATOR:
                break
            header_buffer.write(line)

        header = header_buffer.getvalue()
        if not header:
            self._is_connected = False
            raise ConnectionError("Empty header, disconnected")

        content_length = get_content_length(header)

        # Read body
        content_buffer = BytesIO()
        missing = content_length
        while missing > 0:
            chunk = self.server.stdout.read(missing)
            if not chunk:
                self._is_connected = False
                raise ConnectionError("Server closed connection mid-read")
            content_buffer.write(chunk)
            missing -= len(chunk)

        return content_buffer.getvalue()
