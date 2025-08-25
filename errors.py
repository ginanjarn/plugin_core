"""json-rpc errors"""

from typing import Union, Dict, Any, Optional


class JSONRPCException(Exception):
    """json-rpc exception base"""

    def __init__(self, code: int, message: str, data: Optional[Any] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


ParseError = JSONRPCException(code=-32700, message="parse error")
"""An error occurred while parsing the JSON text"""

InvalidRequest = JSONRPCException(code=-32600, message="invalid request")
"""The JSON sent is not a valid Request object"""

MethodNotFound = JSONRPCException(code=-32601, message="method not found")
"""The method does not exist / is not available"""

InvalidParams = JSONRPCException(code=-32602, message="invalid params")
"""Invalid method parameter(s)"""

InternalError = JSONRPCException(code=-32603, message="internal error")
"""Internal JSON-RPC error"""

ServerNotInitialized = JSONRPCException(-32002, "server not initialized")
"""Server received a notification or request before the server received the `initialize` request"""

UnknownErrorCode = JSONRPCException(-32001, "")

RequestFailed = JSONRPCException(-32803, "request failed")
"""A request failed but it was syntactically correct"""

ServerCancelled = JSONRPCException(-32802, "server cancelled")
"""The server cancelled the request"""

ContentModified = JSONRPCException(-32801, "content modified")
"""The content of a document got modified outside normal conditions"""

RequestCancelled = JSONRPCException(-32800, "request cancelled")
"""The client has canceled a request and a server has detected the cancel"""


class ServerError(JSONRPCException):
    """Reserved for implementation-defined server-errors"""

    min_range = -32099
    max_range = -32000

    def __init__(self, code: int, message: str, data: Optional[Any] = None) -> None:
        if not (self.min_range < code < self.max_range):
            raise ValueError(f"valid code {self.min_range} to {self.max_range}")
        super().__init__(code, message, data)


def transform_error(
    error: Union[JSONRPCException, Exception, None]
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
