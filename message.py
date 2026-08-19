"""JSON-RPC 2.0 message utilities"""

from json import loads, dumps, JSONDecodeError
from typing import Optional, Union, Dict, Any, TypedDict

from .errors import ParseError

# Type aliases
Method = str
Params = Optional[Any]
Result = Optional[Any]
Error = Optional[Dict[str, Any]]


# TypedDicts for clarity
class Notification(TypedDict, total=False):
    jsonrpc: str
    method: Method
    params: Params


class Request(TypedDict, total=False):
    jsonrpc: str
    id: int
    method: Method
    params: Params


class Response(TypedDict, total=False):
    jsonrpc: str
    id: int
    result: Result
    error: Error


JSONRPC_KEY = "jsonrpc"
JSONRPC_VERSION = "2.0"


def new_notification(method: Method, params: Params = None) -> Notification:
    """Create a JSON-RPC notification (no id)."""
    return {JSONRPC_KEY: JSONRPC_VERSION, "method": method, "params": params}


def new_request(id: int, method: Method, params: Params = None) -> Request:
    """Create a JSON-RPC request."""
    return {JSONRPC_KEY: JSONRPC_VERSION, "id": id, "method": method, "params": params}


def new_response(id: int, result: Result = None, error: Error = None) -> Response:
    """Create a JSON-RPC response."""
    if error is not None:
        return {JSONRPC_KEY: JSONRPC_VERSION, "id": id, "error": error}
    return {JSONRPC_KEY: JSONRPC_VERSION, "id": id, "result": result}


def loads_rpc2(json_str: Union[str, bytes]) -> Dict[str, Any]:
    """Load a JSON-RPC 2.0 message.

    Raises:
        ParseError: if JSON parsing fails
        ValueError: if jsonrpc version is invalid
    """
    try:
        dct = loads(json_str)
    except JSONDecodeError as err:
        raise ParseError(str(err)) from err

    if dct.get(JSONRPC_KEY) != JSONRPC_VERSION:
        raise ValueError("Invalid or missing jsonrpc version")

    return dct


def dumps_rpc2(message: Dict[str, Any], as_bytes: bool = False) -> Union[str, bytes]:
    """Dump a JSON-RPC 2.0 message."""
    msg = dict(message)  # copy to avoid mutating caller's dict
    msg[JSONRPC_KEY] = JSONRPC_VERSION
    json_str = dumps(msg)
    return json_str.encode() if as_bytes else json_str
