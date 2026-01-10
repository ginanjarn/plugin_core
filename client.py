"""client object"""

import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, Union
import sublime

from .child_process import ChildProcess
from .diagnostics import ReportSettings
from .errors import MethodNotFound
from .message import (
    MessagePool,
    Method,
    Response,
    Params,
)
from .session import Session
from .transport import Transport

RequestHandler = Callable[[Session, Params], Any]
NotificationHandler = Callable[[Session, Params], None]
ResponseHandler = Callable[[Session, Response], None]
SessionMessageHandler = Union[RequestHandler, NotificationHandler, ResponseHandler]


@dataclass
class ServerArguments:
    command: List[str]
    cwd: Path


@lru_cache
def normalize_method(method: Method) -> str:
    """normalize_method

    Nomalization steps:
    * replace '/' with '_'
    * convert to lower case

    e.g.: textDocument/completion -> textdocument_completion
    """
    return method.replace("/", "_").lower()


class BaseClient:
    """"""

    def __init__(
        self,
        arguments: ServerArguments,
        transport_cls: Transport,
        report_settings: ReportSettings = None,
    ):
        self.server_process = ChildProcess(arguments.command, arguments.cwd)
        self.message_pool = MessagePool(
            transport_cls(self.server_process),
            self.handle,
            self.terminate,
        )

        # server message handler
        self.handler_map: Dict[Method, SessionMessageHandler] = dict()
        self._start_server_lock = threading.Lock()

        self._set_default_handler()

        # session data
        self.session = Session(report_settings=report_settings)

    def _set_default_handler(self):
        """set default handler

        Register class method which has following rule as method handler :
        * method name start with 'handle_'
        * replace '/' with '_'
        * convert to lower case

        example:
          ---------------------------------------------------------
          rpc method                 handler method name
          ---------------------------------------------------------
          textDocument/completion    handle_textdocument_completion
          textDocument/hover         handle_textdocument_hover
          textDocument/codeAction    handle_textdocument_codeaction
          ---------------------------------------------------------

        """

        for name in dir(self):
            attribute = getattr(self, name)
            if not callable(attribute):
                continue

            prefix = "handle_"
            if name.startswith(prefix):
                method = name[len(prefix) :]
                self.handler_map[normalize_method(method)] = attribute

    def handle(self, method: Method, params: Union[Params, Response]) -> Optional[Any]:
        """"""
        try:
            func = self.handler_map[normalize_method(method)]
        except KeyError:
            raise MethodNotFound

        return func(self.session, params)

    def register_handler(self, method: Method, function: SessionMessageHandler) -> None:
        """"""
        self.handler_map[normalize_method(method)] = function

    def start_server(self, env: Optional[dict] = None) -> None:
        """"""
        # only one thread can run server
        if self._start_server_lock.locked():
            return

        with self._start_server_lock:
            if not self.server_process.is_running():
                sublime.status_message("running language server...")
                # sometimes the server stop working
                # we must reset the state before run server
                self.reset_session()

                self.server_process.run(env)
                self.message_pool.listen()

    def reset_session(self) -> None:
        """reset session state"""
        self.session.reset()

    def is_ready(self) -> bool:
        """check session is ready"""
        return self.server_process.is_running() and self.session.is_initialized()

    def terminate(self) -> None:
        """terminate session"""
        self.server_process.terminate()
        self.reset_session()
