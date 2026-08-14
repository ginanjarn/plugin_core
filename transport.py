"""transport handler"""

from abc import ABC, abstractmethod


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
            ConnectionError
            ValueError
        """
