"""Child process handler for managing language server subprocesses."""

import logging
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple, Union

LOGGER = logging.getLogger(__name__)

if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    STARTUPINFO = None


def recover_exception(
    default_factory: Callable[[], Any],
    exceptions: Optional[Union[Exception, Tuple[Exception, ...]]] = None,
):
    """Return default value if exception is raised."""
    exceptions = exceptions or Exception

    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as err:
                LOGGER.debug("Recovering from exception: %s", err)
                return default_factory()

        return inner

    return wrapper


@dataclass
class ProcessOptions:
    @property
    def command(self) -> List[str]:
        raise NotImplementedError("command")

    def update(self, value: "ProcessOptions") -> None:
        raise NotImplementedError("update")


@dataclass
class Module(ProcessOptions):
    python: str
    modname: str
    argv: List[str] = None
    cwd: Optional[str] = None
    env: Optional[dict] = None

    @property
    def command(self) -> List[str]:
        _cmd = [self.python, "-m", self.modname]
        _argv = self.argv or []
        return _cmd + _argv

    def update(self, value: "Module") -> None:
        self.python = value.python or self.python
        self.modname = value.modname or self.modname
        self.argv = value.argv or self.argv
        self.cwd = value.cwd or self.cwd
        self.env = value.env or self.env


@dataclass
class Executable(ProcessOptions):
    executable: str
    argv: List[str] = None
    cwd: Optional[str] = None
    env: Optional[dict] = None

    @property
    def command(self) -> List[str]:
        _argv = self.argv or []
        return [self.executable] + _argv

    def update(self, value: "Executable") -> None:
        self.executable = value.executable or self.executable
        self.argv = value.argv or self.argv
        self.cwd = value.cwd or self.cwd
        self.env = value.env or self.env


def load_options(data: dict) -> ProcessOptions:
    for cls in {Module, Executable}:
        try:
            return cls(**data)
        except Exception:
            pass

    raise TypeError(
        f"Error load options. Data must serialized from {Module, Executable}"
    )


class ChildProcess:
    """Wrapper around subprocess.Popen with safe lifecycle management."""

    def __init__(self, options: ProcessOptions):
        self.options = options
        self.process: Optional[subprocess.Popen] = None

        self._switch_lock = threading.RLock()
        self._is_running = False
        self._stderr_closed_event = threading.Event()

    def is_running(self) -> bool:
        """Check if process is running."""
        with self._switch_lock:
            return self._is_running

    def run(self, options: Optional[ProcessOptions] = None) -> None:
        """Start the child process."""
        with self._switch_lock:
            if self._is_running:
                LOGGER.warning("Process already running, ignoring run()")
                return

            self.options.update(options)
            LOGGER.info("Executing command: %s", shlex.join(self.options.command))

            try:
                self.process = subprocess.Popen(
                    self.options.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=self.options.env,
                    cwd=self.options.cwd,
                    bufsize=0,
                    startupinfo=STARTUPINFO,
                )
            except Exception as err:
                LOGGER.error("Failed to start process: %s", err)
                raise

            threading.Thread(target=self._listen_stderr_task, daemon=True).start()
            threading.Thread(target=self._wait_exit_task, daemon=True).start()

            self._is_running = True

    @property
    @recover_exception(BytesIO)
    def stdin(self):
        return self.process.stdin

    @property
    @recover_exception(BytesIO)
    def stdout(self):
        return self.process.stdout

    @property
    @recover_exception(BytesIO)
    def stderr(self):
        return self.process.stderr

    def _listen_stderr_task(self):
        """Continuously read stderr and log output."""

        def _listen(prefix: str):
            while True:
                line = self.stderr.readline()
                if not line:
                    break
                print(f'{prefix} {line.rstrip().decode(errors="replace")}')

        self._stderr_closed_event.clear()
        prefix = f"[{Path(self.options.command[0]).name}]"
        try:
            _listen(prefix)
        finally:
            self._stderr_closed_event.set()

    def _wait_exit_task(self) -> None:
        """Wait for process exit and trigger termination cleanup."""
        if self.process:
            self.process.wait()
        with self._switch_lock:
            self.terminate()

    def terminate(self) -> None:
        """Terminate the child process gracefully."""
        with self._switch_lock:
            if not self._is_running:
                return
            self._is_running = False

            try:
                if self.process:
                    self.process.terminate()
                    return_code = self.process.wait(timeout=5)
                    LOGGER.info("Process terminated with exit code %s", return_code)
            except subprocess.TimeoutExpired:
                LOGGER.warning("Process did not exit, killing...")
                self.process.kill()
            except Exception as err:
                LOGGER.error("Error terminating process: %s", err)

            # Ensure stderr thread finishes
            self._stderr_closed_event.wait(timeout=2)
            # Release Popen object
            self.process = None
