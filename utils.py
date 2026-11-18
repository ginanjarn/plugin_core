import traceback
from collections import defaultdict
from functools import wraps
from time import monotonic as time_monotonic

import sublime


def on_main_thread(func):
    """Execute function on Sublime's main thread."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        def run():
            try:
                return func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        sublime.set_timeout(run, 0)
        return None  # fire-and-forget

    return wrapper


def on_new_thread(func):
    """Execute function asynchronously on Sublime's worker thread."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        def run():
            try:
                return func(*args, **kwargs)
            except Exception:
                traceback.print_exc()

        sublime.set_timeout_async(run, 0)
        return None  # fire-and-forget

    return wrapper


DEBOUNCE_MAP = defaultdict(lambda: 0)


def debounce(duration: float = 0.5):
    def inner_fn(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _now = time_monotonic()
            if _now < DEBOUNCE_MAP[func]:
                return None

            DEBOUNCE_MAP[func] = _now + duration
            return func(*args, **kwargs)

        return wrapper

    return inner_fn
