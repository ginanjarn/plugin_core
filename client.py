"""client object"""

import threading
from dataclasses import dataclass
from functools import wraps, lru_cache
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, Union
import sublime

from .child_process import ChildProcess
from .errors import MethodNotFound
from .message import (
    MessagePool,
    MethodName,
    Response,
)
from .session import Session
from .transport import Transport


HandleParams = Union[Response, dict]
HandlerFunction = Callable[[Session, HandleParams], Any]


@dataclass
class ServerArguments:
    command: List[str]
    cwd: Path


@lru_cache
def normalize_method(method: MethodName) -> str:
    """normalize_method
    e.g.: textDocument/completion -> textcocument_completion
    """
    return method.replace("/", "_").lower()


class BaseClient:
    """"""

    def __init__(self, arguments: ServerArguments, transport_cls: Transport):
        self.server = ChildProcess(arguments.command, arguments.cwd)
        self.message_pool = MessagePool(transport_cls(self.server), self.handle)

        # server message handler
        self.handler_map: Dict[MethodName, HandlerFunction] = dict()
        self._start_server_lock = threading.Lock()

        self._set_default_handler()

        # session data
        self.session = Session()

    def _set_default_handler(self):
        # Register all callable attribute starts with 'handle_' as default
        # method handler.
        # Method name must following rule:
        #   * replace '/' with '_'
        #   * method start with 'handle_'
        #
        # e.g: textDocument/completion -> textcocument_completion

        for name in dir(self):
            attribute = getattr(self, name)
            if not callable(attribute):
                continue

            prefix = "handle_"
            if name.startswith(prefix):
                method = name[len(prefix) :]
                self.handler_map[method.lower()] = attribute

    def handle(self, method: MethodName, params: HandleParams) -> Optional[Any]:
        """"""
        try:
            func = self.handler_map[normalize_method(method)]
        except KeyError:
            raise MethodNotFound(MethodName)

        return func(self.session, params)

    def register_handler(self, method: MethodName, function: HandlerFunction) -> None:
        """"""
        self.handler_map[normalize_method(method)] = function

    def start_server(self, env: Optional[dict] = None) -> None:
        """"""
        # only one thread can run server
        if self._start_server_lock.locked():
            return

        with self._start_server_lock:
            if not self.server.is_running():
                sublime.status_message("running language server...")
                # sometimes the server stop working
                # we must reset the state before run server
                self.reset_session()

                self.server.run(env)
                self.message_pool.listen()

    def reset_session(self) -> None:
        """reset session state"""
        self.session.reset()

    def is_ready(self) -> bool:
        """check session is ready"""
        return self.server.is_running() and self.session.is_initialized()

    def must_initialized(func):
        """exec if initialized"""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.session.is_initialized():
                return None
            return func(self, *args, **kwargs)

        return wrapper

    def terminate(self) -> None:
        """terminate session"""
        self.server.terminate()
        self.reset_session()
