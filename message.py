"""message"""

from json import loads, dumps, JSONDecodeError
from typing import Optional, Union, Dict, Any

from .errors import ParseError


Method = str
Params = Optional[Any]
Result = Optional[Any]
Error = Optional[Dict[str, Any]]


def new_notification(method: Method, params: Params = None) -> dict:
    return {"method": method, "params": params}


def new_request(id: int, method: Method, params: Params = None) -> dict:
    return {"id": id, "method": method, "params": params}


def new_response(id: int, result: Result = None, error: Error = None) -> dict:
    if error:
        return {"id": id, "error": error}
    return {"id": id, "result": result}


JSONRPC_KEY = "jsonrpc"
JSONRPC_VERSION = "2.0"


def loads_rpc2(json_str: Union[str, bytes]) -> dict:
    """loads json-rpc message

    Raises:
        ParseError: failed to loads json
        ValueError: invalid jsonrpc 2.0
    """

    try:
        dct = loads(json_str)
    except JSONDecodeError as err:
        raise ParseError(str(err)) from err
    try:
        if dct[JSONRPC_KEY] != JSONRPC_VERSION:
            raise ValueError("invalid json-rpc version")
    except KeyError as err:
        raise ValueError("invalid json-rpc version") from err

    return dct


def dumps_rpc2(message: dict, as_bytes: bool = False) -> Union[str, bytes]:
    """dumps json-rpc message"""

    message[JSONRPC_KEY] = JSONRPC_VERSION
    json_str = dumps(message)
    if as_bytes:
        return json_str.encode()
    return json_str
