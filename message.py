"""message"""

from dataclasses import dataclass, asdict
from json import (
    loads as json_loads,
    dumps as json_dumps,
    JSONDecodeError,
)
from typing import Optional, Union, Dict, Any

from .errors import ParseError


Method = str
Params = Optional[Any]
Result = Optional[Any]
Error = Optional[Dict[str, Any]]


@dataclass
class Message:
    """JSON-RPC Message interface"""


@dataclass
class Notification(Message):
    method: Method
    params: Params = None


@dataclass
class Request(Message):
    id: int
    method: Method
    params: Params = None


@dataclass
class Response(Message):
    id: int
    result: Result = None
    error: Error = None


JSONRPC_KEY = "jsonrpc"
JSONRPC_VERSION = "2.0"


def loads(json_str: Union[str, bytes]) -> Message:
    """loads json-rpc message

    Raises:
      * json.JsonDecodeError if fail loads json
      * ValueError if invalid jsonrpc version
    """

    try:
        dct = json_loads(json_str)
    except JSONDecodeError as err:
        raise ParseError(str(err)) from err

    version = dct.pop(JSONRPC_KEY, "1.0")
    if version != JSONRPC_VERSION:
        raise ValueError("invalid json-rpc version")

    # Request and Notification contain 'method' key
    if "method" in dct:
        if "id" in dct:
            return Request(**dct)
        return Notification(**dct)
    return Response(**dct)


def dumps(message: Message, as_bytes: bool = False) -> Union[str, bytes]:
    """dumps json-rpc message"""

    dct = asdict(message)
    dct[JSONRPC_KEY] = JSONRPC_VERSION

    if isinstance(message, Response):
        # Response only contain one of 'result' or 'error' field
        if not message.error:
            del dct["error"]
        else:
            del dct["result"]

    json_str = json_dumps(dct)
    if as_bytes:
        return json_str.encode()
    return json_str
