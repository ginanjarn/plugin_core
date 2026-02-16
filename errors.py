"""json-rpc errors"""

from functools import partial
from typing import Union, Dict, Any, Optional


class JSONRPCException(Exception):
    """json-rpc exception base"""

    def __init__(self, message: str, code: int, data: Optional[Any] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


ParseError = partial(JSONRPCException, code=-32700)
"""An error occurred while parsing the JSON text"""

InvalidRequest = partial(JSONRPCException, code=-32600)
"""The JSON sent is not a valid Request object"""

MethodNotFound = partial(JSONRPCException, code=-32601)
"""The method does not exist / is not available"""

InvalidParams = partial(JSONRPCException, code=-32602)
"""Invalid method parameter(s)"""

InternalError = partial(JSONRPCException, code=-32603)
"""Internal JSON-RPC error"""

ServerNotInitialized = partial(JSONRPCException, code=-32002)
"""Server received a notification or request before the server received the `initialize` request"""

UnknownErrorCode = partial(JSONRPCException, code=-32001)

RequestFailed = partial(JSONRPCException, code=-32803)
"""A request failed but it was syntactically correct"""

ServerCancelled = partial(JSONRPCException, code=-32802)
"""The server cancelled the request"""

ContentModified = partial(JSONRPCException, code=-32801)
"""The content of a document got modified outside normal conditions"""

RequestCancelled = partial(JSONRPCException, code=-32800)
"""The client has canceled a request and a server has detected the cancel"""


class ServerError(JSONRPCException):
    """Reserved for implementation-defined server-errors"""

    min_range = -32099
    max_range = -32000

    def __init__(self, message: str, code: int, data: Optional[Any] = None) -> None:
        if not (self.min_range < code < self.max_range):
            raise ValueError(f"valid code {self.min_range} to {self.max_range}")
        super().__init__(message, code, data)


def transform_error(
    error: Union[JSONRPCException, Exception, None],
) -> Optional[Dict[str, Any]]:
    """transform exception to rpc error"""

    if not error:
        return None

    try:
        code = error.code
        message = error.message

    except AttributeError:
        # 'err.code' and 'err.message' may be not defined
        code = InternalError.code
        message = repr(error)

    return {"code": code, "message": message}
