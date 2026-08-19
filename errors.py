"""JSON-RPC error definitions and utilities."""

from typing import Union, Dict, Any, Optional


class JSONRPCException(Exception):
    """Base class for JSON-RPC exceptions."""

    def __init__(self, message: str, code: int, data: Optional[Any] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class ParseError(JSONRPCException):
    """An error occurred while parsing the JSON text."""

    def __init__(self, message: str = "Parse error", data: Optional[Any] = None):
        super().__init__(message, -32700, data)


class InvalidRequest(JSONRPCException):
    """The JSON sent is not a valid Request object."""

    def __init__(self, message: str = "Invalid request", data: Optional[Any] = None):
        super().__init__(message, -32600, data)


class MethodNotFound(JSONRPCException):
    """The method does not exist / is not available."""

    def __init__(self, message: str = "Method not found", data: Optional[Any] = None):
        super().__init__(message, -32601, data)


class InvalidParams(JSONRPCException):
    """Invalid method parameter(s)."""

    def __init__(self, message: str = "Invalid params", data: Optional[Any] = None):
        super().__init__(message, -32602, data)


class InternalError(JSONRPCException):
    """Internal JSON-RPC error."""

    def __init__(self, message: str = "Internal error", data: Optional[Any] = None):
        super().__init__(message, -32603, data)


class ServerError(JSONRPCException):
    """Reserved for implementation-defined server-errors."""

    min_range = -32099
    max_range = -32000

    def __init__(self, message: str, code: int, data: Optional[Any] = None) -> None:
        if not (self.min_range <= code <= self.max_range):
            raise ValueError(
                f"Valid code range is {self.min_range} to {self.max_range}"
            )
        super().__init__(message, code, data)


def transform_error(
    error: Union[JSONRPCException, Exception, None],
) -> Optional[Dict[str, Any]]:
    """Transform an exception into a JSON-RPC error dict."""
    if error is None:
        return None

    if isinstance(error, JSONRPCException):
        return {"code": error.code, "message": error.message, "data": error.data}

    # Fallback for generic exceptions
    return {"code": -32603, "message": repr(error)}
