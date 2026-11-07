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
    command: List[str]
    cwd: Optional[Path] = None
    env: Optional[dict] = None

    def __post_init__(self):
        if not isinstance(self.command, list):
            raise TypeError(f"invalid 'command' type: expected {list}")
        self.command = [str(el) for el in self.command]

    def update(self, value: Optional["ProcessOptions"]) -> None:
        if not value:
            return
        self.command = value.command or self.command
        self.cwd = value.cwd or self.cwd
        self.env = value.env or self.env


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
