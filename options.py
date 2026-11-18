"""Language client options"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .child_process import ChildProcess, ProcessOptions, load_options
from .transport_stdio import StandardIO


class TransportKind(IntEnum):
    Ipc = 1
    Socket = 2


@dataclass
class ServerOptions:
    transport_kind: TransportKind
    options: Optional[dict] = None
    _process: Optional[object] = field(default=None, init=False)

    def get_options(self) -> ProcessOptions:
        return load_options(self.options)

    def get_process(self) -> ChildProcess:
        if self._process:
            return self._process

        self._process = ChildProcess(self.get_options())
        return self._process

    def get_transport(self):
        if self.transport_kind == TransportKind.Ipc:
            return StandardIO(self.get_process())
        raise ValueError(f"Unsupported transport kind: {self.transport_kind}")


@dataclass
class ClientOptions:
    settings_basename: str = "PluginCore.sublime-settings"
    command_name: str = "plugin_core"
