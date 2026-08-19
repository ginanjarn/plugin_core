"""Transport handler abstraction"""

from abc import ABC, abstractmethod


class Transport(ABC):
    """Abstract base class for transport implementations.

    A Transport defines how to connect to a server, exchange data,
    and manage connection lifecycle. Subclasses should implement
    concrete mechanisms (e.g., stdio, sockets, websockets).
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the server.

        Raises:
            ConnectionError: if unable to connect.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the server and release resources."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if transport is currently connected."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write raw bytes to the server.

        Args:
            data: Serialized message to send.

        Raises:
            ConnectionError: if not connected or write fails.
        """

    @abstractmethod
    def read(self) -> bytes:
        """Read raw bytes from the server.

        Returns:
            content: The received message as bytes.

        Raises:
            ConnectionError: if not connected or read fails.
            ValueError: if message framing/parsing fails.
        """
