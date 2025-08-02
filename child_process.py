"""child process handler"""

import os
import shlex
import subprocess
import threading
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Union, Callable, Any

if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    # Hide created process window
    STARTUPINFO.dwFlags |= subprocess.SW_HIDE | subprocess.STARTF_USESHOWWINDOW
else:
    STARTUPINFO = None


def recover_exception(
    default_factory: Callable[[Any], Any],
    *,
    exceptions: Optional[Union[Exception, tuple]] = None,
):
    """return default value if exception raised

    Arguments:
        default_factory: factory of default value
        excepttions: captured exceptions

    Returns:
        default_factory() result
    """

    # default
    exceptions = exceptions or Exception

    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions:
                return default_factory()

        return inner

    return wrapper


class ChildProcess:
    """Child Process"""

    def __init__(self, command: List[str], cwd: Optional[Path] = None):
        if not isinstance(command, list):
            raise ValueError("command value must list of str")

        self.command = command
        self.cwd = cwd

        self.process: subprocess.Popen = None
        self._run_event = threading.Event()

        # Prevent run process until termination done
        self._terminate_event = threading.Event()
        self._terminate_event.set()

    def is_running(self) -> bool:
        """If process is running"""
        return bool(self.process) and self.process.poll() is None

    def wait_process_running(self) -> None:
        """Wait process running"""
        self._run_event.wait()

    def run(self, env: Optional[dict] = None) -> None:
        """Run process"""

        # Wait if in termination process
        self._terminate_event.wait()

        # Prevent process reassignment
        if self.process and self.process.poll() is None:
            return

        print("execute '%s'" % shlex.join(self.command))

        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env or None,
            cwd=self.cwd or None,
            shell=True,
            bufsize=0,
            startupinfo=STARTUPINFO,
        )

        # Ready to call 'Popen()' object
        self._run_event.set()

        thread = threading.Thread(target=self._listen_stderr_task)
        thread.start()

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
        prefix = f"[{self.command[0]}]"
        while bline := self.stderr.readline():
            print(prefix, bline.rstrip().decode())

        # Stderr return empty character, process is terminated
        self._terminate_event.set()

    def terminate(self) -> None:
        """Terminate process"""

        self._terminate_event.clear()
        self._run_event.clear()

        if not self.process:
            return

        self.process.kill()
        return_code = self.process.wait()
        print("process terminated with exit code", return_code)
        # Set to None to release 'Popen()' object from memory
        self.process = None
