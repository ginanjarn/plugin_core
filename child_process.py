"""child process handler"""

import os
import shlex
import subprocess
import threading
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional, Union, Callable, Any

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
        # lock for run() and terminate() call
        self._switch_lock = threading.RLock()
        self._is_running = False
        self._stderr_closed_event = threading.Event()

    def is_running(self) -> bool:
        """If process is running"""
        with self._switch_lock:
            return self._is_running

    def run(self, env: Optional[dict] = None) -> None:
        """Run process"""

        with self._switch_lock:
            # Prevent process reassignment
            if self._is_running:
                return

            print("execute '%s'" % shlex.join(self.command))

            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env or None,
                cwd=self.cwd or None,
                bufsize=0,
                startupinfo=STARTUPINFO,
            )

            thread1 = threading.Thread(target=self._listen_stderr_task, daemon=True)
            thread2 = threading.Thread(target=self._wait_exit_task, daemon=True)

            thread1.start()
            thread2.start()
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
        self._stderr_closed_event.clear()

        prefix = f"[{self.command[0]}]"
        try:
            while bline := self.stderr.readline():
                print(prefix, bline.rstrip().decode())

        finally:
            # Stderr return empty character, process is terminated
            self._stderr_closed_event.set()

    def _wait_exit_task(self) -> None:
        """call terminate() on broken child"""
        self.process.wait()

        with self._switch_lock:
            self.terminate()

    def terminate(self) -> None:
        """Terminate process"""

        with self._switch_lock:
            if not self._is_running:
                return
            self._is_running = False

            self.process.terminate()
            return_code = self.process.wait()
            print("process terminated with exit code", return_code)

            # wait until stderr closed
            self._stderr_closed_event.wait()
            # Set to None to release 'Popen()' object from memory
            self.process = None
